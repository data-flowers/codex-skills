"""Offline regression tests: run with python3 -m unittest discover -s scripts/tests."""
import contextlib
import csv
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_ptah_dataset as audit
import gemini_rewrite_common as common
import optimize_airtable_attachments as attachments
import rewrite_ai_context_gemini as single
import rewrite_ai_context_gemini_batched as batch
import rewrite_descriptions_gemini as descriptions

BODY = '\n\n'.join(f'## {heading}\nNot explicit in source.' for heading in single.EXPECTED_HEADINGS)
DESCRIPTION = 'Builds industrial sensors that detect machine faults across factories.'


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(socket, 'socket', side_effect=AssertionError('Tests must not use the network')).start()

    def csv(self, rows, filename='input.csv'):
        path = self.root / filename
        fields = list(dict.fromkeys(key for row in rows for key in row))
        common.write_csv(path, fields, rows)
        return path

    def run_rewrite(self, module, rows=None, extra=(), payload=None):
        source = self.csv(rows or [{'Id': '001', 'Name': 'Example', 'Website': 'https://example.test',
                                   'Description': '', 'Private Notes': 'PRIVATE_CANARY'}])
        args = ['--input-csv', str(source), '--output-csv', str(self.root/'out.csv'), '--cache-dir', str(self.root/'cache'),
                '--request-delay-seconds', '0', '--context-columns', 'Name,Website', *extra]
        payload = payload if payload is not None else {'description': DESCRIPTION, '_usage_metadata': {'promptTokenCount': 123}}
        with patch.object(common, 'require_api_key', return_value='FAKE'), patch.object(common, 'call_gemini_json', side_effect=payload if callable(payload) else None, return_value=payload) as call:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = module.main(args)
        report = json.loads((self.root/'cache/usage-summary.json').read_text())
        return code, call, report, common.load_csv(self.root/'out.csv')[1]

    def full_row(self):
        row = {field['canonical']: '' for field in audit.CONTRACT['fields']}
        row.update(id='001', name='Example', description=DESCRIPTION, categoryId='Companies', subcategories=['Sensors'])
        return row

    def gate(self, rows, extra=(), kind='canonical'):
        source = self.root/'data.json'
        source.write_text(json.dumps(rows))
        with patch.object(sys, 'argv', ['audit', str(source), '--kind', kind, *map(str, extra)]), contextlib.redirect_stdout(io.StringIO()) as out:
            code = audit.main()
        return code, json.loads(out.getvalue())

    def taxonomy(self):
        path = self.root/'taxonomy.json'
        path.write_text(json.dumps({'version': 1, 'categories': {'Companies': ['Sensors']}}))
        return path


class RewriteTests(OfflineTest):
    def test_uncached_description_completes_and_preserves_id(self):
        code, call, report, rows = self.run_rewrite(descriptions)
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]['Id'], '001')
        self.assertEqual(rows[0]['Description'], DESCRIPTION)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(report['usage']['promptTokenCount'], 123)
        self.assertNotIn('PRIVATE_CANARY', call.call_args.kwargs['prompt'])

    def test_cached_run_reports_zero_new_usage(self):
        self.run_rewrite(descriptions)
        _, call, report, _ = self.run_rewrite(descriptions)
        self.assertEqual(call.call_count, 0)
        self.assertEqual(report['api_calls'], 0)
        self.assertEqual(report['cache_hits'], 1)
        self.assertEqual(report['usage'], {})

    def test_limit_applies_after_id_selection(self):
        rows = [{'Id':key,'Name':'Example','Website':'','Description':''} for key in ('a','b')]
        _, call, _, output = self.run_rewrite(descriptions, rows=rows, extra=['--id','b','--limit','1'])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(output[0]['Description'], '')
        self.assertEqual(output[1]['Description'], DESCRIPTION)

    def test_changed_source_invalidates_cache(self):
        self.run_rewrite(descriptions)
        _, call, _, _ = self.run_rewrite(descriptions, rows=[{'Id': '001', 'Name': 'Renamed', 'Website': 'https://example.test'}])
        self.assertEqual(call.call_count, 1)

    def test_all_runners_require_explicit_columns(self):
        for module in (single, batch, descriptions):
            with self.subTest(module=module.__name__), patch.object(common, 'call_gemini_json') as call:
                with self.assertRaisesRegex(ValueError, 'context-columns'):
                    self.run_rewrite(module, extra=['--context-columns', ''])
                call.assert_not_called()

    def test_missing_selected_column_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'Columns not found'):
            self.run_rewrite(batch, extra=['--context-columns', 'Name,Typo'])

    def test_context_cap_rejects_before_requests(self):
        with self.assertRaisesRegex(ValueError, 'max-context-chars'):
            self.run_rewrite(batch, extra=['--max-context-chars', '3'])

    def test_blank_and_duplicate_ids_fail_before_batch(self):
        for ids in ([''], ['a', 'a']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.run_rewrite(batch, rows=[{'Id': key, 'Name': 'Example', 'Website': ''} for key in ids])

    def test_ai_context_rejects_fences_and_markdown_links(self):
        for text in ('```markdown\n' + BODY + '\n```', BODY + '\n[link](//example.test)'):
            with self.assertRaises(ValueError):
                single.validate_markdown(text)

    def test_single_and_batch_keep_sources_outside_target(self):
        raw = {'markdown': BODY, 'source_links': ['https://example.test']}
        for module, payload in ((single, raw), (batch, {'results': [{'id': '001', **raw}]})):
            with self.subTest(module=module.__name__):
                _, _, _, rows = self.run_rewrite(module, payload=payload, extra=['--force'])
                self.assertEqual(rows[0]['AI Context'], BODY)
                cached = common.load_cached_result(self.root/'cache', '001')
                self.assertEqual(cached['raw_response']['source_links'], ['https://example.test'])

    def test_empty_link_selection_means_no_links(self):
        self.assertEqual(common.choose_context_columns(['Website', 'Private Notes'], []), [])
        _, call, _, _ = self.run_rewrite(single, payload={'markdown': BODY}, extra=['--link-columns', '', '--context-columns', 'Name'])
        self.assertNotIn('https://example.test', call.call_args.kwargs['prompt'])

    def test_validation_retry_counts_every_response(self):
        responses = iter([{'results': [], '_usage_metadata': {'promptTokenCount': 10}},
                          {'results': [{'id': '001', 'markdown': BODY}], '_usage_metadata': {'promptTokenCount': 20}}])
        _, call, report, _ = self.run_rewrite(batch, payload=lambda **kwargs: next(responses))
        self.assertEqual(call.call_count, 2)
        self.assertEqual(report['api_calls'], 2)
        self.assertEqual(report['retries'], 1)
        self.assertEqual(report['usage']['promptTokenCount'], 30)

    def test_duplicate_returned_ids_are_retried(self):
        rows = [{'Id': key, 'Name': 'Example', 'Website': ''} for key in ('a', 'b')]
        responses = iter([{'results': [{'id': 'a', 'markdown': BODY}]*2},
                          {'results': [{'id': key, 'markdown': BODY} for key in ('a', 'b')]}])
        _, call, _, out = self.run_rewrite(batch, rows=rows, payload=lambda **kwargs: next(responses))
        self.assertEqual(call.call_count, 2)
        self.assertTrue(all(row['AI Context'] == BODY for row in out))

    def test_http_failure_stops_without_repeated_quota_requests(self):
        def fail(**kwargs):
            raise common.GeminiGenerationError('quota', status=429)
        with self.assertRaises(common.GeminiGenerationError):
            self.run_rewrite(batch, payload=fail)
        report = json.loads((self.root/'cache/usage-summary.json').read_text())
        self.assertEqual(report['api_calls'], 1)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['usage_unavailable_calls'], 1)

    def test_invalid_json_retains_response_usage(self):
        response = {'usageMetadata': {'promptTokenCount': 12}, 'candidates': [{'content': {'parts': [{'text': '{bad'}]}}]}
        fake = SimpleNamespace(read=lambda: json.dumps(response).encode())
        with patch.object(common.request, 'urlopen', return_value=contextlib.nullcontext(fake)):
            with self.assertRaises(common.GeminiGenerationError) as error:
                common.call_gemini_json(api_key='FAKE', model='fake', system_instruction='', prompt='')
        self.assertEqual(error.exception.usage, {'promptTokenCount': 12})

    def test_config_and_cli_override(self):
        source = self.csv([{'Id': 'a', 'Name': 'Example'}])
        config = self.root/'config.json'
        config.write_text(json.dumps({'input_csv': source.name, 'output_csv': 'configured.csv', 'cache_dir': 'configured-cache',
                                      'context_columns': 'Name', 'request_delay_seconds': 0}))
        with patch.object(common, 'require_api_key', return_value='FAKE'), patch.object(common, 'call_gemini_json', return_value={'description': DESCRIPTION}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            descriptions.main(['--config', str(config), '--output-csv', str(self.root/'overridden.csv')])
        self.assertTrue((self.root/'overridden.csv').exists())
        self.assertFalse((self.root/'configured.csv').exists())

    def test_failure_preserves_completed_cache_and_csv(self):
        rows = [{'Id': key, 'Name': 'Example', 'Website': ''} for key in ('a', 'b')]
        def respond(**kwargs):
            if not common.cache_path(self.root/'cache', 'a').exists():
                return {'description': DESCRIPTION}
            raise common.GeminiGenerationError('stop', status=401)
        with self.assertRaises(common.GeminiGenerationError):
            self.run_rewrite(descriptions, rows=rows, payload=respond)
        self.assertIsNotNone(common.load_cached_result(self.root/'cache', 'a'))
        self.assertTrue((self.root/'out.csv').exists())


class CacheTests(OfflineTest):
    def test_distinct_opaque_ids_have_distinct_files(self):
        self.assertNotEqual(common.cache_path(self.root, 'Org/A'), common.cache_path(self.root, 'org-a'))
        common.save_cached_result(self.root, 'Org/A', {'description': 'first'})
        common.save_cached_result(self.root, 'org-a', {'description': 'second'})
        self.assertEqual(common.load_cached_result(self.root, 'Org/A')['description'], 'first')

    def test_opaque_ids_are_distributed_deterministically(self):
        shards = [next(i for i in range(4) if common.in_shard(key, 4, i)) for key in ['alpha', 'beta', 'gamma', 'delta']]
        self.assertGreater(len(set(shards)), 1)
        for key in ('alpha', 'Org/A', '001'):
            self.assertEqual(sum(common.in_shard(key, 4, i) for i in range(4)), 1)

    def test_malformed_cache_is_a_miss(self):
        common.cache_path(self.root, 'a').write_text('{broken')
        with self.assertWarns(UserWarning):
            self.assertIsNone(common.load_cached_result(self.root, 'a'))

    def test_wrong_cache_identity_is_a_miss(self):
        common.cache_path(self.root, 'a').write_text(json.dumps({'cache_key': 'b'}))
        with self.assertWarns(UserWarning):
            self.assertIsNone(common.load_cached_result(self.root, 'a'))

    def test_atomic_failure_preserves_existing_file(self):
        path = self.root/'existing.csv'
        path.write_text('old')
        with patch.object(common.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                common.atomic_write_text(path, 'new')
        self.assertEqual(path.read_text(), 'old')
        self.assertEqual(list(self.root.iterdir()), [path])


class DatasetTests(OfflineTest):
    def test_incomplete_contract_cannot_publish(self):
        code, report = self.gate([{'id':'a','name':'Example','description':DESCRIPTION,'categoryId':'Companies','subcategories':['Sensors']}], ['--require-gate','publication'])
        self.assertEqual(code, 2)
        self.assertFalse(report['gates']['publicationReady'])
        self.assertIn('websiteUrl', report['checks']['contractShape']['missingFields'])

    def test_valid_contract_and_taxonomy_can_publish_with_optional_blanks(self):
        code, report = self.gate([self.full_row()], ['--require-gate','publication','--taxonomy',self.taxonomy()])
        self.assertEqual(code, 0)
        self.assertTrue(report['gates']['publicationReady'])
        self.assertEqual(report['evidenceReview']['status'], 'unverified')

    def test_publication_requires_taxonomy_membership_check(self):
        code, report = self.gate([self.full_row()], ['--require-gate','publication'])
        self.assertEqual(code, 3)
        self.assertFalse(report['gates']['taxonomyMembershipVerified'])

    def test_invalid_pair_fails(self):
        row = self.full_row(); row['subcategories'] = ['Wrong']
        code, report = self.gate([row], ['--taxonomy',self.taxonomy()])
        self.assertEqual(code, 2)
        self.assertEqual(len(report['checks']['invalidTaxonomyPairs']), 1)

    def test_contract_shape_is_checked_per_row(self):
        row = self.full_row(); del row['websiteUrl']; row['id'] = '002'
        code, report = self.gate([self.full_row(), row])
        self.assertEqual(code, 2)
        self.assertTrue(report['checks']['contractShape']['missingFieldRows'])

    def test_auto_kind_keeps_canonical_with_publication_control(self):
        self.assertEqual(audit.infer_kind('auto', [*self.full_row(), 'Published']), 'canonical')

    def test_id_only_delta_is_not_a_change(self):
        code, report = self.gate([{'Id':'001'}], kind='delta')
        self.assertEqual(code, 2)
        self.assertTrue(report['checks']['contractShape']['noChangedFields'])

    def test_malformed_taxonomy_has_a_clear_error(self):
        path = self.root/'bad-taxonomy.json'; path.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'Taxonomy requires'):
            audit.load_taxonomy(path)

    def test_delta_only_needs_key_and_changed_fields(self):
        code, report = self.gate([{'Id':'001','Description':DESCRIPTION}], kind='delta')
        self.assertEqual(code, 0)
        self.assertFalse(report['gates']['publicationReady'])

    def test_upload_protected_fields_fail(self):
        code, _ = self.gate([{'Id':'001','Logo':''}], kind='delta')
        self.assertEqual(code, 2)

    def test_current_and_future_year_guards_remain(self):
        year = audit.datetime.now(audit.timezone.utc).year
        for value in (str(year), str(year+1)):
            row = self.full_row(); row['yearFounded'] = value
            code, report = self.gate([row], ['--require-gate','publication','--taxonomy',self.taxonomy()])
            self.assertNotEqual(code, 0)
            self.assertFalse(report['gates']['publicationReady'])

    def test_nested_and_legacy_state_hashes(self):
        state = self.root/'state.json'
        for shape in ({'version':2,'hashes':{'canonical':'old'}}, {'version':1,'canonicalHash':'old'}):
            state.write_text(json.dumps(shape))
            self.assertTrue(audit.state_drift(state, {}, 'new')['stale'])

    def test_upload_does_not_compare_canonical_hash(self):
        state = self.root/'state.json'
        state.write_text(json.dumps({'version':1,'canonicalHash':'canonical','hashes':{'uploadArtifact':'upload'}}))
        self.assertFalse(audit.state_drift(state, {}, 'upload', kind='upload')['stale'])

    def test_state_for_another_artifact_is_not_compared(self):
        state = self.root/'state.json'
        state.write_text(json.dumps({'version':2,'sourceOfTruth':'other.json','hashes':{'canonical':'old'}}))
        self.assertFalse(audit.state_drift(state, {}, 'new', input_path=self.root/'data.json')['checked'])

    def test_state_drift_is_separate_from_data_validity(self):
        state = self.root/'state.json'; state.write_text(json.dumps({'canonicalHash':'old'}))
        code, report = self.gate([self.full_row()], ['--state',state,'--taxonomy',self.taxonomy(),'--require-gate','publication'])
        self.assertEqual(code, 0)
        self.assertTrue(report['checks']['stateFreshness']['stale'])


class AttachmentTests(OfflineTest):
    def fixture(self):
        source = self.root/'source.png'; source.write_bytes(b'original')
        output = self.root/'optimized.webp'; output.write_bytes(b'optimized')
        args = SimpleNamespace(manifest=self.root/'manifest.json', id_field='Id', source_field='Logo',
                 source_root=self.root, max_dimension=256, quality=84, require_opaque=False,
                 refresh_remote_sources=False, magick='MOCK')
        image = {'id':'a','source':str(source),'original':{'sha256':attachments.sha256(source.read_bytes())},
                 'optimized':{'path':str(output),'bytes':9,'sha256':attachments.sha256(output.read_bytes())}}
        policy = {'maximumWidth':256,'maximumHeight':256,'quality':84,'requireOpaque':False,'format':'WebP',
                  'autoOrient':True,'stripMetadata':True,'preserveAspectRatio':True,'upscale':False}
        args.manifest.write_text(json.dumps({'images':[image], 'policy':policy, 'errorCount':0}))
        return args, source, image

    def reused(self, args, rows):
        with patch.object(attachments, 'identify', return_value={'format':'WEBP','width':128,'height':128,'opaque':True}), patch.object(attachments, 'prepare', side_effect=lambda args, rows, reusable: reusable):
            return attachments.reuse_manifest(args, rows)

    def test_unchanged_asset_is_reused(self):
        args, source, image = self.fixture()
        self.assertEqual(self.reused(args, [{'Id':'a','Logo':str(source)}]), [image])

    def test_changed_source_identity_is_rebuilt(self):
        args, _, _ = self.fixture()
        self.assertEqual(self.reused(args, [{'Id':'a','Logo':'https://example.test/new.png'}]), [])

    def test_changed_source_bytes_are_rebuilt(self):
        args, source, _ = self.fixture(); source.write_bytes(b'changed')
        self.assertEqual(self.reused(args, [{'Id':'a','Logo':str(source)}]), [])

    def test_changed_transform_policy_is_rebuilt(self):
        args, source, _ = self.fixture(); args.quality = 80
        self.assertEqual(self.reused(args, [{'Id':'a','Logo':str(source)}]), [])

    def test_prepare_only_transforms_changed_rows(self):
        args, source, image = self.fixture()
        image.update(name='Example', savedBytes=0, compressionPercent=0)
        image['original']['bytes'] = 9
        args.output_dir = self.root/'images'; args.workers = 1; args.progress_every = 25
        args.name_field = 'Name'; args.input = self.root/'input.csv'
        changed = {**image, 'id':'b'}
        rows = [{'Id':'a','Name':'Example','Logo':str(source)}, {'Id':'b','Name':'New','Logo':'new.png'}]
        with patch.object(attachments, 'optimize_one', return_value=changed) as transform, patch.object(attachments.subprocess, 'run', return_value=SimpleNamespace(stdout='Mock ImageMagick\n')), contextlib.redirect_stdout(io.StringIO()):
            manifest = attachments.prepare(args, rows, reusable=[image])
        self.assertEqual(transform.call_count, 1)
        self.assertEqual(transform.call_args.args[0]['Id'], 'b')
        self.assertEqual(manifest['sourceCount'], 2)
        self.assertEqual(manifest['processedCount'], 2)
        self.assertEqual(manifest['reusedCount'], 1)

    def test_remote_refresh_is_explicit(self):
        args, _, image = self.fixture()
        data = json.loads(args.manifest.read_text()); data['images'][0]['source'] = 'https://example.test/logo.png'
        args.manifest.write_text(json.dumps(data)); rows = [{'Id':'a','Logo':'https://example.test/logo.png'}]
        self.assertEqual(len(self.reused(args, rows)), 1)
        args.refresh_remote_sources = True
        self.assertEqual(self.reused(args, rows), [])


if __name__ == '__main__':
    unittest.main()
