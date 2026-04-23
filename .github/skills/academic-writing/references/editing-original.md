# Editing Advice (Highly Idiosyncratic)

**Source:** https://www.csc2.ncsu.edu/faculty/mpsingh/local/advice/editing.html

A foolish consistency is the hobgoblin of little minds,adored by little statesmen and philosophers and divines.--Ralph Waldo Emerson, Self-Reliance

This page is meant for my advisees. It enumerates several grammatical, stylistic, and other habits I have acquired about writing, editing, and presenting over the years. They may seem idiosyncratic in some cases, but often there is method to my madness. Even when these editing habits are idiosyncratic, I will insist on them.

To my advisees who might find these demands onerous: These are merely elements of the pursuit of perfection. I want you to develop an eye for detail. I should point out that I learned most of the following simply from observing good practices, not from being told. The fact that I am telling you in considerable detail is a great favor I do you: You should be so happy to learn these good practices that you wouldn't think of questioning any of the following recommendations now :-). (Seriously, though, I am surprised that I have to point you to this page again and again.)

An important observation: You simply have no choice but to learn to get your grammar and the rest of writing straight. You cannot outsource it. In particular, professional dissertation editors, who make a business of fixing students' writing, often leave some presentational errors and, worse, introduce technical errors and ambiguities. I am saying this on an evidence of one for a dissertation editor that a student of mine used plus several instances of professional editing I have seen my own and others' writing go through. Professional editors can help, but you remain responsible for what you write.

---

## Notes on Writing

1. See my page on [Guidelines for Writing Papers](https://www.csc2.ncsu.edu/faculty/mpsingh/local/advice/writing.html).
2. Be willing to reorganize your paper and rewrite large parts of it. It is generally a bad idea to get attached to some phrasing. Mark Twain once recommended that authors should find their favorite sentence in whatever they wrote and delete it.
3. Spell check the whole document; then proof read it. It is rude to off-load this task on your readers (unless as a special request to proof read some writing after you have already proof read it yourself). Some reviewers will be quite offended to see bugs that you should have caught.
4. Don't hesitate to get other students to comment on your work. They can help identify potential problems with the exposition or the content that you or I may not notice.
5. Reusing your own prose is potentially tricky. It is OK to share text between an externally submitted or published paper and an internal document (thesis, dissertation, written prelim, technical report). Specifically, a submission can be identical to a TR. However, there should not be two concurrent external submissions of the same material or a submission after a separate publication. It is OK to share across workshops and conferences, but a short note in the paper (indicating overlap) is appropriate. When you work on a new topic or have sufficiently new results, but with a similar motivation and technical framework as before, it is tempting to reuse old prose. In my experience, it is better to rewrite the motivation, because each (intended) target audience is different. For the technical framework, it might be OK to reuse older (debugged) descriptions as background with acknowledgment of previous publication. This assumes there are enough new results in the rest of the paper. The justification for reuse is that you can't be expected to invent, e.g., a new temporal logic, in each paper. Moreover, you can relate your new work more easily to the existing body of work by using the framework used in the existing work. Of course, this presumes your interesting results are not in the logic per se.
6. Remember to acknowledge any financial support you receive through the university. Ask me for the numbers (IDs) of any grants that may have supported your work. Thank others who gave you comments. Don't thank your coauthors! If you thank some people, spell their names correctly, and use their given names and last names. For anonymous submissions, include the text but comment it out so it is ready to be uncommented when the paper is accepted.

---

## Word Processing

1. Use Latex and Bibtex for any serious writing.
2. Use the style of any conference that you are targeting. I suggest ACM because it has a fussy bibliography checker that will catch errors others may miss.
3. Overleaf is the popular way to prepare Latex documents. Overleaf complicates a few things but its convenience overall for collaborative work makes it a winner.
4. Change the main document in an Overleaf project to be the current one. I suggest a name other than the default main.tex. Also check that the TeX Live version is the latest available.
5. Don't place styles in your project that are part of the Latex distribution. For example, IEEE and ACM are part of the Latex distribution. Including your copies in the best case has no benefit (but causes clutter) and in the worst case tells Overleaf to use the obsolete version you included instead of the latest one available.
6. As for software in general, warnings are a sign that something is off. Make an effort to clear all of them. The only warnings that should remain are if you are being compelled to use a style that is not compatible with the latest distributions.
7. I suggest cloning your Overleaf project to a folder on your computer. You might sometimes edit there; at least, it's a backup when you want to work offline.
8. Always include the title, your name, and date on the title page.
9. Number all pages, preferably at bottom center. Some official styles remove page numbers but you can add them back until you are submitting a final, accepted paper.

---

## General Editing

1. Place whitespace immediately before an open parenthesis or brace or bracket, but not immediately after. Citations typically come out in brackets, so leave a space before each of them.
2. Don't place whitespace immediately before a closing parenthesis or brace or bracket, but do place a space or a punctuation character immediately after. Citations typically come out in brackets, so leave a space or a punctuation character after each of them.
3. Place whitespace immediately after a comma, a colon, a period, or a semicolon, but none immediately before them.
4. Don't use footnotes. Decide if it is worth stating in the main text; if not, don't say it.
5. (Mike Huhns) Place a table's caption at the top.
6. Place a figure's caption at the bottom. Don't also have a caption within the figure—a risk when you draw it separately and are including it in the paper. For separate figure files, name the files systematically.
7. Write all captions in sentence case: first letter (of first word) upper case, all else lower case. End with a period (change of mind from my previous guidance). As an aside, you can have long captions to explain a figure right there, although generally you would put the explanations in the main text.
8. Almost always, you should refer to a figure from the main text. The publication Nature doesn't do that, but most will require it. It is a good idea even if not required—otherwise your readers may be confused about why you included a certain figure.
9. Use a single closing quote (') to mean an apostrophe, e.g., "Bob's car." An opening quote does not an apostrophe make.
10. Don't use too many contractions. In particular, never use contractions such as "we'll," "I'll," "we've," and so on (not even in a draft paper). For more formal work, don't even use "don't," "doesn't," "can't," and "won't." And don't ever use "u" and "ur" in any writing where there is the slightest risk that I might see it.
11. Don't use numerals in text for the smaller numbers. For example, don't say "the agent talks to 3 other agents." Some publications use words for numbers ten and smaller. That is a good strategy. Conversely, don't spell out a large number such as 157. It would be quite odd to read "our experiments involved one hundred fifty seven agents."
12. Write numbers larger than or equal to 1,000 with a comma at the thousands place and in positions at multiples of three. But write years without commas.
13. Don't begin a sentence with a lowercase letter.
    - For example, if you are saying something about a technical word or a word in your program that begins with a lowercase letter, try to work in another word in front of it. For example, try not to write "serviceProvider refers to ..."; instead write "The serviceProvider field refers to ..." I might accept something like "eBay" where it is an established brand name though it would always jar. Uniformity throughout a document is key even in such a case.
    - For example, if you are referring to a work by an author whose last name begins with a particle such as "van" or "de" capitalize it when you place it at the beginning of a sentence, as in "Van Riemsdijk et al. [2017] show that, in contrast, ..." and sometimes (for Dutch names especially) even in the middle of a sentence "In contrast, Van Riemsdijk et al. [2017] show that ..." unless we also include the author's first name, which we would rarely if ever do. For other languages, we might not capitalize the particle mid sentence but would capitalize it at the start of a sentence.
14. Don't begin a sentence with a numeral.
15. Don't begin a sentence with a citation.
16. Don't begin a sentence with a bracket or parenthesis.
17. When introducing a new term, don't use quotes; italicize the term instead. In general, the fewer the quoted terms the better.
18. In US usage, quotes apply in a noncontext free manner with respect to commas and periods. For example, you would write ``this.'' and ``this,'' even though these are not context free in the sense of formal grammar. The idea is that reducing the white space visible above the punctuation makes the text look better, at least once you get used to it.
19. In the rare case where you must use a footnote, do not place its superscript (in the main text) just before a comma or period. This too is US usage (see above for quotes).
20. In the rare case where you must use a footnote, do not place its superscript (in the main text) just after a space or anything that translates to a space, e.g., as a line break does in Latex.
21. List three or more items with commas all the way: "A, B, and C" but not "A, B and C" unless B and C together are one thing. In that case, in some situations it might be better to phrase this as "B and C, and A" (which deviates from this rule a little by using a comma even when there are two items involved).
22. Go easy on the subscripts. Latex makes it attractive to write complex formulas, but complex formulas are never attractive. Don't over-complicate your notation.
23. Keep simple line-drawings in figures—clutter arises easily if one is not careful and is not easy on the reader. Boxes with shadings rarely look good in a paper—too industrial and too much like a presentation. Scanned in figures are rarely appropriate except for early drafts—and for early drafts even scanned in hand drawings should be fine.
24. Use the same typeface for text in figures as in the main paper (times works well for both—even if they are slight variants of each other).
25. Use a smallish type size for the text in figures, e.g., 10 or 9pt. The main text of your paper will range from 10pt to 12pt, so 10pt in the figures will be ideal.
26. Draw figures to be about 3.25in wide or about 5.5in wide. The former can fit in a two column format and save space. Doing so is often a consideration for most conference submissions. The latter can fit in the Springer Lecture Notes format, also a common format for computer science publications.
27. Color is fine, but relying on it is risky, because many readers will print your paper on black-and-white printers. So you can't exploit color in the text (e.g., by saying, "the green box") and you ought to check that the greyscale version of the color is OK. Also, remember that some readers are color blind. However, color is useful when available, because it can highlight some relationships—so use color but make sure the paper is comprehensible in greyscale, e.g., by adding another feature such as dashes.
28. For an in-text formula, put any ending parentheses on the same line as the rest of the formula—i.e., split the formula somewhere other than at the last parenthesis or even the last few parentheses.
29. Treat all items in the same item list alike in terms of capitalization.
30. Capitalize sections, subsections, subsubsections (i.e., make first letter of all big or important words upper case).
31. When referring to a section, figure, table, chapter, algorithm, or protocol, capitalize it, e.g., "Figure 4 illustrates this point," but not otherwise, e.g., "the following figures show ..."
32. Use sentence case for paragraph headings and end each heading with a period.
33. End all items in an item list with or without periods (preferably with).
34. A document node (e.g., section) should either have no children (e.g., subsections) or have two or more children.
35. Item lists and enumerations should have two or more entries.
36. Use emphasis fonts, e.g., italics or bold, only for a few words or phrases.
37. I generally prefer to leave names of disciplines such as "computer science" in lower case, instead of "Computer Science." My rationale is that too many capitalized words spoil readability. Further, capitalization makes concepts appear more grand than they are.
38. Here are some words to capitalize carefully both in main paper and your bibliographic entries:
    - Internet.
    - Web.
    - eBay.
    - BERT.
    - Names of people and adjectives based on names, e.g., Bayes, Bayesian, and Boolean.
39. When a whole sentence is parenthetical, the period that ends the sentence goes within the parentheses.

---

## LaTeX-Specific Points

1. Write an en-dash as "--" with no spaces on either end. Thus "11--23" will appear as "11–23" and that's how you want it. Likewise, write an em-dash as "---" with no spaces on either end.
2. Use quotes as ``correct''—LaTeX will then print them correctly, although they might look weird on a browser. By contrast, LaTeX will print "wrong" as having closing quotes on either side.
3. For a figure file to be included in LaTeX, make its name match the internal LaTeX label for the figure. Make the file name an English word (or words separated by hyphens), so the file name can spell check properly.
4. Insert a space in references: "Chapter3 discusses" => "Chapter 3 discusses." In LaTeX, this means you would place a tilde before any \ref, as in "Section~\ref{sec-foo}."
5. Don't use hard constants for internal references in the paper. Use something like "Section~\ref{sec-foo} shows," which should expand to the correct section number and with a space to boot. Likewise, "Figure~\ref{fig-foo} illustrates ..." The tilde (~) is a so-called tie in LaTeX. It forces the characters of either side of it to be typeset with an intervening space but on the same line. Using it helps avoid poor typesetting, e.g., where the last word of a line or page is "Figure" and the first word of the next line or page is "4."
6. Avoid expressions such as "the following figures" or "the above figures" because (1) LaTeX may place the figures differently from what you might expect when you edit the file or change the style and (2) you may move text around and suddenly find these implicit references (i.e., "above" and "following") to be out of whack.
7. Where appropriate use \texttt{...} to place a term or expression in typewriter (aka teletype or tt) font. This is good for small code-like text. I have recently taken to using \textsf{...} for the above purposes—this yields narrower text and seems to typeset better than \texttt. For URLs and even snippets that are not URLs (e.g., r/CMV), it is better to enclose them in \url{}, which typesets them correctly and avoids line overflows.
8. Don't use math fonts for identifiers that are longer than a letter. That is, $FP$ is wrong. It shows up with a large gap between the F and the P. Instead use \emph{FP} or even \textit{FP} in normal text and \textit{FP} if you need to enclose it in a mathematical formula or another mathematical environment. When you need such an identifier as a subscript or superscript, enclose it in \mathrm as in $Q_{\mathrm{FP}}$.
9. When you have identifiers for which you need numerals, such as agents A1 and A2, write these with subscripts as in $A_1$ and $A_2$. When you have multiword identifiers you will need additional markup to prevent the default LaTeX math font from kicking in. You might use $\textrm{ABC}_1$ or $\textit{ABC}_1$. Or, you might place the subscript alone in math as in ABC$_1$.
10. For large formulas (with multiple subscripts), use \[ \] or other display modes in LaTeX to make sure they are large enough to read.

---

## References

1. Use BibTeX, of course. For some purposes, I use biblatex and biber, which too uses bibliography entries in the BibTeX format.
2. Place your own bib entries in a separate file, ideally named your-first-name.bib, your-last-name.bib, or even your-eos-login-ID.bib (least preferred, since this ID won't generally be a name). Capitalize the file name so we can have a spell checker learn it.
3. Do not copy over bib entries from my file into yours. Duplicate versions generate spurious warnings and are difficult to maintain. Periodically, I may want to clean up the entries you made and add them to one of my files. You have access to my files, of course.
4. Do not hardcode your bibliography path into the LaTeX command for inserting a bibliography. Instead, use an environment variable that LaTeX uses to access the correct bibliography files. On Windows, this is the variable BIBINPUTS; using it enables us both to work on the same document without having to edit the path repeatedly.
5. By default, use fullname references, readily generated using `\usepackage[square]{natbib}` and `\bibliographystyle{plainnat}` in the preamble and end of the LaTeX source files.
6. When the required style is not compatible with the above, you can still include the names of authors in the main text so that it reads something like "Singh et al. [11] claim ...".
7. To use BibTeX correctly, you must put each reference into an entry of the correct kind, e.g., @book, @article, @inproceedings, and others.
8. Use braces { } for each field with a string instead of double quotes.
9. For fields with a number (e.g., year, chapter, volume, number), just write the number (no braces or quotes).
10. For fields with defined symbols, use the symbol (no braces or quotes). The most important case of symbols is the month field: use a three-letter month name (e.g., jan) and let BibTeX expand it as appropriate for the current style. You can also define your own symbols. For example, I define and use LNCS for the famous Springer series.
11. Supply correct names for the publication forum (e.g., journal), appropriately capitalized. In particular, the booktitle, title, and journal fields should be in title case. DBLP often doesn't provide correct capitalizations so you cannot rely on it.
12. BibTeX (when used with the common BibTeX styles) converts all article and chapter titles (but not booktitles) to sentence case. This normalization can mess up the capitalization of some words. To make sure that certain words (such as Internet) are capitalized or are written in mixed case (such as tModel), enclose the entire word in braces, e.g., {Internet}. In more detail, `title = {Life on the {Internet}}`. If the bib style a publisher required were to force the entire title into uppercase, the above won't work, but I haven't encountered such a style. A safer style would be {I}nternet, but I don't like this because it makes checking spellings harder. An unacceptably poor style is to enclose the entire title in double braces, since doing so precludes BibTeX from changing the capitalization at all.
13. If a title field contains a colon, write the next word is capitalized, even if it is "A". For example, `title = {Life on the {Internet}: A Brief Report}`. Oddly enough, BibTeX is confused by question marks in a title, so you need braces for the following word, as in `title = {Life on the {Internet}? {An} Impossible Idea}`. Without these braces, it would print "An" in lowercase.
14. Remove redundant info, which most prominently shows up in proceedings booktitle fields. "Proceedings of the 2022 Conference on Foo (Foo 2022)" could be shortened to "Proceedings of the Conference on Foo (Foo)" even if it is not the official title. Also, Springer has the bad habit of putting dates and locations in titles and DBLP puts them in booktitle. Remove that information and place in month, year, and address fields.
15. BibTeX has a flaw in that it confuses the location of a conference with the location of the publisher using the address field for both. I suppose specific styles could do better but most don't as far as I know. I adopted the convention of using address to mean conference location since that is more informative than knowing that ACM (for example) is based in New York.
16. Supply page numbers. For the newer styles and publishing practices (such as ACM's) also supply (if available) the articleno and numpages fields. Some styles can use that information.
17. Supply a DOI if one exists; if not, and an ISBN (for a book) or URL exists, add it. If a DOI is known, exclude the URL and ISBN.
18. For collections, supply an editor; for proceedings you don't need to and I never do.
19. For collections and books, supply a publisher. Use a short name for the publisher as in my bib file. Supply an address for the publisher as a city name; the state and country name are not needed for well-known cities, e.g., "Berlin" is good enough—you don't need "Berlin, Germany."
20. Use full first names of authors (along with middle initials and full last name), not "G.B. Shaw" but "George B. Shaw" or even "George Bernard Shaw" (if, like Ralph Waldo Emerson, the author is known with their full middle name).
21. End each initial with a period.
22. For multiple authors or editors, BibTeX uses `{First1 M1. Last1 and First2 M2. Last2 and First3 M3. Last3 and First4 M4. Last4}`. The correct entries are generated from the above syntax; by contrast, if you start with `{First1 M1. Last1, First2 M2. Last2, First3 M3. Last3, and First4 M4. Last4}` it acts as if you have two authors, one with a long, weird name. Good examples are in the bib files I post.
23. First authors with names with suffixes must be treated specially; see my bib files; look for "Petrie, Jr.," for example.
24. For a version to be published, it is good practice to include BibTeX's output bibliography into the LaTeX file and post-edit it if necessary. Doing so has the benefit of freezing the bibliography as part of the document, even if you were to modify your bib files later. Overleaf has an option to download the .bbl file for your project and then you have to copy its contents into the LaTeX source in lieu of the \bibliography command.

---

## Drawing Tools

I don't use drawing tools any more for serious writing and prefer to produce my diagrams using tikz, a LaTeX package that helps high-quality pictures and enables using LaTeX fonts and math. But here are some points for the cases where you use drawing tools.

1. When you are drawing, make the grid visible to simplify alignment.
2. Use boxes of a reasonably large size.
3. Align all boxes on grid lines.
4. Make sure that the boxes are of the same width and height, especially those within the same column and row, respectively.
5. Place all connectors (lines) on connection points.
6. To that end, make connection points visible and insert connection points on box edges if you need to.
7. You can copy the boxes and drums from my older diagrams for simplicity.
8. Make sure the connectors go on the grid lines.
9. Magnify to 400% to check alignment.
