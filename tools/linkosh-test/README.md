> **Current implementation:** Linkosh has been modified in place for memory-only ingestion. Follow [MEMORY_INGESTION.md](MEMORY_INGESTION.md). The original setup instructions below describe the earlier SQLite-based version.

# LinkedIn ingestion test: WSL files, Windows Chrome

Prepared Linkosh prerelease: v0.1.1. No Node build or Linux browser is needed.

## Install the prepared extension

In Windows Chrome, using the profile where you sign into LinkedIn:

1. Open chrome://extensions.
2. Enable Developer mode.
3. Click Load unpacked.
4. In the folder picker, paste this path into the address bar, press Enter, and select the folder:

~~~text
\\wsl$\Ubuntu\home\shibu\cs\hackathons\orma\tools\linkosh-test\extension
~~~

The same extension folder in Ubuntu is:

~~~text
/home/shibu/cs/hackathons/orma/tools/linkosh-test/extension
~~~

Keep this folder in place after loading it; reloading the same installation preserves its extension identity.

## Capture one small LinkedIn sample

1. Open https://www.linkedin.com/my-items/saved-posts/ in the same Chrome profile. Sign in yourself if needed.
2. Open Linkosh's Options (right-click its toolbar icon, or use Details > Extension options on chrome://extensions).
3. Under Services, enable only LinkedIn.
4. Under Developer, enable Test mode (about 100 items) and Capture mode.
5. Open Linkosh, select LinkedIn, and click Sync once.
6. Capture mode stores raw response pages without populating the library. After capture finishes, click Ingest raw in Linkosh's developer row to parse those pages without fetching them again.
7. Open Options > Developer > Export database and save linkosh.sqlite.

If Ingest raw is not visible, confirm Capture mode is enabled and reopen the popup.
If Sync fails, record the exact error text and stop; repeated retries are not a useful test.
No saved posts have been imported during setup.

## Put the export in WSL

In Chrome's save dialog you can use:

~~~text
\\wsl$\Ubuntu\home\shibu\cs\hackathons\orma\tools\linkosh-test\exports
~~~

If Chrome downloaded it to Windows Downloads, copy it from an Ubuntu terminal:

~~~bash
cp /mnt/c/Users/shibu/Downloads/linkosh.sqlite \
  /home/shibu/cs/hackathons/orma/tools/linkosh-test/exports/
~~~

## Inspect locally in Ubuntu

~~~bash
cd /home/shibu/cs/hackathons/orma/tools/linkosh-test
python3 inspect_linkedin.py exports/linkosh.sqlite
~~~

The script uses Python's standard library, opens the database read-only, and makes no network requests.
It creates a new folder under reports/ containing:

- coverage.json: counts of populated fields, text lengths, available columns, and captured raw-page counts.
- sample-posts.json: up to 20 normalized LinkedIn records, including their actual captured text.
- compare-with-linkedin.csv: a worksheet for comparing those records with the original posts.

Both saved posts and saved LinkedIn Learning items can be returned by the connector; inspect collection and kind to distinguish them.

## What to compare

Open a short post, a long post with See more, an image post, and a document/carousel post from the captured sample.
Compare the actual summary text with the expanded original. Check whether images are only thumbnail URLs,
whether all document pages exist, and whether video entries contain any transcript.
A nonempty summary or an image URL is not proof that complete content was captured.

Raw captures are kept so we can later distinguish content missing from LinkedIn's response
from content omitted by Linkosh's parser. Reports do not print raw authentication headers.
Keep exports and reports local; both may contain private saved content.

The downloaded release checksum matched:
3768052d91b47c5072669e70a5c93157884e8b7db4c15038ffef20a68d3b4efe

Upstream release: https://github.com/sabyasachi/linkosh/releases/tag/v0.1.1
