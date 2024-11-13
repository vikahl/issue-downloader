# issue-downloader

Cli tool and library to download issues to Markdown file.

The motivation/use case is to have files that can be archived and referenced
even if the repositories themselves are removed or merged.

The script currectly supports Github.

## Usage

```
$ issue-downloader github --help
Usage: issue-downloader github [OPTIONS]

  Sync issues to local files

Options:
  --token TEXT                Github PAT token, can be obtained by 'gh auth
                              token'  [required]
  --org TEXT                  Download issues for this organisation.Mutually
                              exclusive to --repo.
  --repo TEXT                 Specify repos to download form. Specified in the
                              form org/repo
  --date [%Y-%m-%d]           Download issues updated on or after this date.
  --resume / --no-resume      Resume from last downloaded date.  [default: no-
                              resume]
  --archived / --no-archived  Include archived repositories  [default:
                              archived]
  --closed / --no-closed      Include closed issues  [default: closed]
  --save-dir PATH             Directory to save the issues  [default:
                              /home/viktora/vikahl/issue-downloader]
  --formats [MD|JSON]         Limit formats to save. Defaults to MD & JSON
                              formats if not set
  --url TEXT                  URL to the Github api  [default:
                              https://api.github.com/]
  --help                      Show this message and exit.
```
