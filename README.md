# zim-plugin-append
Makes adding text to Zim pages from the command line (or another unix process) possible without further user interaction.

# Usage

NB: many of the options are not implemented due to zim plugin interface limitations.

```
usage: zim --plugin append [OPTIONS]

Options:
	--early,	-0	Apply the text to the *VERY* start of the page (before the header).
	--prefix,	-1	Apply the text to the beginning of the page (rather than the end)
	--attach=<arg>,	-a	Even absent some text to append, attach this file to the page.
	--create,	-c	Only create a new page, do not append to an existing one.
	--clipboard,	-C	Use the system clipboard as a source of text for this page
	--directory=<arg>,	-d	Even absent some text to append, attach every file in the given directory to the page.
	--exists,	-e	Only add to a pre-existing page, do not create one
	--file=<arg>,	-f	Use the contents of the given file as the source of text to apply to the page (can be repeated).
	--help,	-?	Print this help text and exit.
	--header=<arg>,	-h	Seek and append-to the specified header (creating it if need be)
	--journal,	-j	Use todays journal page as a target
	--date=<arg>,	-k	Use a different days journal page as a target (specified as "YYYY-mm-dd")
	--literal=<arg>,	-l	Use the given string (passed as a parameter) as the text to apply to the page.
	--notebook=<arg>,	-N	Select the notebook that the page is in
	--oldline,	-n	Dont add newlines that (ordinarily) would make the incoming text well-spaced with the current page content
	--page=<arg>,	-p	The full page name that the text (and/or files) should be applied to
	--quote,	-q	Wrap the appended text in a big block-quote (or similar)
	--raise,	-r	Request that Zim be brought forward to the users attention (implies "show")
	--show,	-s	Navigate Zim to the specified page (but the window may still be buried)
	--time,	-t	Include the current time (if today's journal page), or the full date and time (otherwise) before the entry
	--usage,	-?	Print this help text and exit.
```

# Examples

Make a note, that right 'now' something has happened:
> zim --plugin append -j -t -l "Went to buy bread."

...the same, but using the long options:
> zim --plugin append --journal --time --literal="Went to buy bread."

