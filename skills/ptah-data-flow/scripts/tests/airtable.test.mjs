import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { CONTRACT, parseAirtableUrl, parsePositiveInt, fetchJson } from '../airtable_common.mjs';
import { auditTable, main as schemaMain } from '../audit_airtable_schema.mjs';
import { buildPlan } from '../mutate_airtable_schema.mjs';
import { prepareFieldPayload, validateSchema, validateInput, loadCsvRows, main } from '../upsert_airtable_csv.mjs';

const table = (idType = 'singleLineText') => ({id:'tblExample', name:'Organizations', fields: CONTRACT.map(field => ({id:`fld${field.canonical}`, name:field.name, type:field.name === 'Id' ? idType : field.acceptedTypes[0]}))});
const fields = (types = {}) => new Map(table().fields.map(field => [field.name, {...field, type:types[field.name] || field.type}]));

test('numeric Id schema is blocked in audit and mutation plan', () => {
  assert.equal(auditTable(table('number')).status, 'blocked');
  assert.ok(buildPlan(table('number')).notes.some(note => note.field === 'Id'));
});
test('valid text Id and native timestamp schema is clean', () => assert.equal(auditTable(table()).status, 'clean'));
test('computed timestamp type remains mandatory', () => {
  const target = table(); target.fields.find(field => field.name === 'Updated At').type = 'dateTime';
  assert.equal(auditTable(target).status, 'blocked');
});
test('Id leading zeros and opaque text are preserved', () => {
  for (const Id of ['001', 'Org/A', 'org-a']) assert.equal(prepareFieldPayload({Id}, ['Id'], fields()).Id, Id);
});
test('numeric identifier serialization is rejected', () => {
  assert.throws(() => prepareFieldPayload({Id:'001'}, ['Id'], fields({Id:'number'})), /Unexpected Id type/);
});
test('blank and populated logos are rejected by general imports', () => {
  for (const Logo of ['', 'https://example.test/logo.png']) {
    assert.throws(() => prepareFieldPayload({Logo}, ['Logo'], fields({Logo:'multipleAttachments'})), /protected/);
    assert.throws(() => validateInput(['Id','Logo'], [{Id:'001',Logo}], ['Id']), /protected/);
  }
});
test('other attachment fields are also rejected', () => {
  assert.throws(() => prepareFieldPayload({Photos:''}, ['Photos'], new Map([['Photos',{type:'multipleAttachments'}]])), /protected/);
});
test('computed fields cannot enter an upload', () => assert.throws(() => validateInput(['Id','Updated At'], [{Id:'001'}], ['Id']), /protected/));
test('narrow payload omits unrelated fields', () => {
  assert.deepEqual(prepareFieldPayload({Id:'001',Description:'Updated',Logo:'stale',Name:'Unchanged'}, ['Id','Description'], fields()), {Id:'001',Description:'Updated'});
});
test('empty values preserve existing fields unless explicitly cleared', () => {
  assert.deepEqual(prepareFieldPayload({Id:'001',Description:''}, ['Id','Description'], fields()), {Id:'001'});
  assert.deepEqual(prepareFieldPayload({Id:'001',Description:''}, ['Id','Description'], fields(), ['Description']), {Id:'001',Description:null});
});
test('merge key must exist in CSV and remote metadata', () => {
  assert.throws(() => validateInput(['Name'], [{Name:'Example'}], ['Id']), /missing merge key/);
  assert.throws(() => validateSchema(table(), ['Name'], ['Id']), /missing merge key/);
});
test('blank and duplicate keys are rejected', () => {
  assert.throws(() => validateInput(['Id'], [{Id:''}], ['Id']), /nonblank/);
  assert.throws(() => validateInput(['Id'], [{Id:'001'},{Id:'001'}], ['Id']), /Duplicate/);
  assert.throws(() => validateInput(['Id'], [{Id:'001'}], []), /nonempty/);
  assert.throws(() => validateInput(['Id'], [{Id:'001'}], ['Id'], ['Id']), /cannot be cleared/);
});
test('checkbox conversion agrees with contract', () => {
  const map = new Map([['Published',{type:'checkbox'}]]);
  for (const input of ['true','yes','checked']) assert.equal(prepareFieldPayload({Published:input}, ['Published'], map).Published, true);
  assert.equal(prepareFieldPayload({Published:'false'}, ['Published'], map).Published, false);
});
test('multiselect values use the Web API string-array shape', () => {
  const map = new Map([['Tech Capabilities',{type:'multipleSelects',options:{choices:[{name:'Sensors'},{name:'Vision'}]}}]]);
  assert.deepEqual(prepareFieldPayload({'Tech Capabilities':'Sensors; Vision'}, ['Tech Capabilities'], map), {'Tech Capabilities':['Sensors','Vision']});
  assert.throws(() => prepareFieldPayload({'Tech Capabilities':'Other'}, ['Tech Capabilities'], map), /Unknown select choice/);
});
test('CLI argument and Airtable URL validation', () => {
  assert.throws(() => parsePositiveInt('1oops','limit'));
  assert.throws(() => parseAirtableUrl('https://example.test/appExample/tblExample'));
  assert.deepEqual(parseAirtableUrl('https://airtable.com/appExample/tblExample/viwExample'), {baseId:'appExample',tableId:'tblExample',viewId:'viwExample'});
});

async function environment(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ptah-node-test-'));
  t.after(() => fs.rm(root, {recursive:true,force:true}));
  const original = {argv:process.argv, fetch:globalThis.fetch, token:process.env.AIRTABLE_TOKEN, log:console.log, error:console.error};
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url, options});
    const data = options.method === 'PATCH' ? {records:JSON.parse(options.body).records, updatedRecords:['recExample']} : {tables:[table()]};
    return {ok:true, text:async () => JSON.stringify(data)};
  };
  process.env.AIRTABLE_TOKEN = 'SYNTHETIC_TEST_TOKEN';
  console.log = console.error = () => {};
  t.after(() => {
    process.argv = original.argv; globalThis.fetch = original.fetch;
    if (original.token === undefined) delete process.env.AIRTABLE_TOKEN; else process.env.AIRTABLE_TOKEN = original.token;
    console.log = original.log; console.error = original.error;
  });
  return {root, calls};
}

test('known-record update executes one narrow PATCH with no metadata request', async t => {
  const {root,calls} = await environment(t);
  const csv = path.join(root,'delta.csv'); await fs.writeFile(csv,'Record Id,Description\nrecExample,Updated\n');
  const boundary = path.join(root,'boundary.json'); await fs.writeFile(boundary,JSON.stringify({version:1,baseId:'appExample',table:table()}));
  process.argv = ['node','upsert','--base','appExample','--table','tblExample','--csv',csv,'--boundary',boundary,'--record-id-column','Record Id','--execute'];
  await main();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, 'PATCH');
  assert.deepEqual(JSON.parse(calls[0].options.body),{records:[{id:'recExample',fields:{Description:'Updated'}}]});
});
test('wrong boundary target is rejected without requests', async t => {
  const {root,calls} = await environment(t);
  const csv = path.join(root,'delta.csv'); await fs.writeFile(csv,'Id,Description\n001,Updated\n');
  const boundary = path.join(root,'boundary.json'); await fs.writeFile(boundary,JSON.stringify({version:1,baseId:'appOther',table:table()}));
  process.argv = ['node','upsert','--base','appExample','--table','tblExample','--csv',csv,'--boundary',boundary,'--execute'];
  await assert.rejects(main(), /does not match/);
  assert.equal(calls.length, 0);
});
test('missing CSV key is rejected before schema or write requests', async t => {
  const {root,calls} = await environment(t);
  const csv = path.join(root,'delta.csv'); await fs.writeFile(csv,'Name,Description\nExample,Updated\n');
  process.argv = ['node','upsert','--base','appExample','--table','tblExample','--csv',csv,'--execute'];
  await assert.rejects(main(), /missing merge key/);
  assert.equal(calls.length, 0);
});
test('full-schema upsert sends endpoint-safe batches and preserves text keys', async t => {
  const {root,calls} = await environment(t);
  const csv = path.join(root,'delta.csv'); await fs.writeFile(csv,'Id,Description\n'+Array.from({length:11}, (_,i)=>`${String(i).padStart(3,'0')},Updated`).join('\n'));
  process.argv = ['node','upsert','--base','appExample','--table','tblExample','--csv',csv,'--execute','--throttle-ms','1'];
  await main();
  assert.equal(calls.length,3);
  const writes = calls.slice(1).map(call=>JSON.parse(call.options.body));
  assert.deepEqual(writes.map(write=>write.records.length), [10,1]);
  assert.equal(writes[0].records[0].fields.Id,'000');
  assert.deepEqual(writes[0].performUpsert,{fieldsToMergeOn:['Id']});
});
test('malformed CSV row widths and duplicate headers are rejected', async t => {
  const {root} = await environment(t);
  for (const value of ['Id,Name\na,b,c\n','Id,Id\na,b\n']) {
    const csv=path.join(root,'bad.csv'); await fs.writeFile(csv,value);
    await assert.rejects(loadCsvRows(csv));
  }
});
test('quoted CSV newlines and commas remain intact', async t => {
  const {root} = await environment(t);
  const csv=path.join(root,'quoted.csv'); await fs.writeFile(csv,'Id,Description\n001,"line 1, detail\nline 2"\n');
  assert.equal((await loadCsvRows(csv)).records[0].Description,'line 1, detail\nline 2');
});
test('uncertain mutations are never retried implicitly', async t => {
  const {calls} = await environment(t);
  globalThis.fetch = async (...args) => {calls.push(args); throw new Error('connection lost');};
  await assert.rejects(fetchJson('https://example.test','FAKE',{method:'PATCH',body:{records:[]}}), /connection lost/);
  assert.equal(calls.length, 1);
});

test('schema CLI returns failure status for a blocked schema', async t => {
  await environment(t);
  globalThis.fetch = async () => ({ok:true,text:async () => JSON.stringify({tables:[table('number')]})});
  process.argv = ['node','schema','--base','appExample','--table','tblExample','--json'];
  assert.equal(await schemaMain(), 2);
});
