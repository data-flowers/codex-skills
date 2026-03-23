# Prompt starters

Most people using this skill are doing one of three things:

- starting with a messy file or folder and trying to turn it into something usable
- picking back up after a run got interrupted
- sanity-checking whether the current dataset is actually done

You should not need to explain the whole workflow every time.
A short prompt is enough. The skill should pick up the rest from the working area, existing artifacts, and the progress log.

## 1. Start a new run

```text
Raw data is in /path/to/data. Make it Ptah-ready.
```

Use this when you're starting from raw files.

## 2. Finish an interrupted run

```text
There was an unexpected error. Finish what you were doing.
```

Use this when something already ran and you just want it to finish the job.

## 3. Review the current dataset

```text
Review the current dataset and tell me if it's Ptah-ready.
```

Use this when you want a clear answer on whether the dataset is actually ready.

## 4. Work against an existing Airtable target

```text
Work with this Airtable: https://airtable.com/app.../tbl.../viw...
```

Use this when you already have an Airtable table in mind.
The skill should then record the Airtable target, ask for the PAT, and continue from the remote boundary.

## 5. Check Airtable status

```text
Check Airtable status.
```

Use this when the current run already has an Airtable target and you want a quick boundary check.
