"""Word list used by stylometry_lr.py (the "AI vocabulary" features).

EXCESS_STYLE_WORDS: the 407 words annotated `type == "style"` in
`results/excess_words.csv` of https://github.com/berenslab/llm-excess-vocab
(commit 53db991afc251782106cd817a1c3fa47a4d41781, file SHA-256 prefix f5786f3cc83f9578), the
annotated list of words with excess usage in PubMed abstracts published with
Kobak, Gonzalez-Marquez, Horvat, Lause, "Delving into LLM-assisted writing in biomedical
publications through excess vocabulary", Science Advances 11(27), 2025 (arXiv 2406.07016).
The rows annotated "content" (462, mostly biomedical topics), "content/style",
"style/content", "style/count" and "other" are left out. Lower-cased, sorted, otherwise
unchanged.

Licence of the source repository: MIT, Copyright (c) 2024 Dmitry Kobak, Rita
Gonzalez-Marquez. The list is copied here under that licence, whose notice follows.

  Permission is hereby granted, free of charge, to any person obtaining a copy of this
  software and associated documentation files (the "Software"), to deal in the Software
  without restriction, including without limitation the rights to use, copy, modify, merge,
  publish, distribute, sublicense, and/or sell copies of the Software, and to permit
  persons to whom the Software is furnished to do so, subject to the following conditions:
  The above copyright notice and this permission notice shall be included in all copies or
  substantial portions of the Software.
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
  INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
  PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
  FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
  DEALINGS IN THE SOFTWARE.
"""

EXCESS_STYLE_WORDS: tuple[str, ...] = tuple("""
accentuates achieving acknowledges acknowledging across additionally address addresses
addressing adept adhered adhering advancement advancements advancing advocates advocating
affirming afflicted aiding aims akin align aligning aligns alongside amid amidst analysis
announced apologizes approach assess assessed assessing assessments attains attributed
augmenting avenue avenues based between bolster bolstered bolstering both broader burgeoning
capabilities capitalizing categorized categorizes categorizing challenge challenges combating
commendable compelling complex complicates complicating comprehend comprehending comprehensive
comprising conditions conducted consequently consolidates contributing conversely correlating
crafted crafting crucial culminating customizing declare declared deductively delineates delve
delved delves delving demonstrated demonstrates demonstrating dependability dependable despite
detailing detrimentally diminishes diminishing discern discerned discernible discerning
displaying disrupts distinct distinctions distinctive diverse during easing effectively elevate
elevated elevates elevating elucidate elucidates elucidating embracing emerged emerges
emphasises emphasising emphasize emphasizes emphasizing employed employing employs empowers
emulating emulation enabling encapsulates encompass encompassed encompasses encompassing
endangering endeavors endeavours enduring enhance enhanced enhancements enhances enhancing
ensuring equipping escalating essentials evaluates evolving exacerbating examines exceeding
excels exceptional exceptionally exerting exhibit exhibited exhibiting exhibits expedite
expediting exploration explores facilitated facilitates facilitating featuring fight findings
focusing formidable fostering fosters foundational furnish garnered garnering gauged grappling
groundbreaking groundwork hardest harness harnesses harnessing heighten heightened highlight
highlighting highlights hinder hinges hinting hold holds however identified illuminates
illuminating imbalances impact impactful impacting impede impeding imperative impressive
inadequately including incorporates incorporating indicating individuals influencing inherent
initially innovative inquiries insights integrates integrating integration interconnectedness
interplay into intricacies intricate intricately introduces invaluable investigates involves
involving juxtaposed leading leverages leveraging like limitations linked maintaining merges
methodologies meticulous meticulously midst multifaceted necessitate necessitates necessitating
necessity need notable notably noteworthy nuanced nuances observed offer offering offers
optimizing orchestrating outcomes outlines overlook overlooking overwhelmed particularly paving
persist pinpoint pinpointed pinpointing pioneering pioneers pivotal poised pose posed poses
posing postponed potential potentially precise predominantly presents preserving pressing
prevalent primarily primary promise promising pronounced propelling providing realizes realm
realms recognizing refine refines refining reframing remains remarkable renowned research
resulting rethink revealed revealing reveals revolutionize revolutionizing revolves role
scrutinize scrutinized scrutinizing seamless seamlessly seeks serves serving shaping shedding
showcased showcases showcasing signifying solidify spanned spanning specifically spurred stands
statement stemming strategically strategies streamline streamlined streamlines streamlining
struggle subsequently substantial substantiated substantiates surged surmount surpass surpassed
surpasses surpassing swift swiftly techniques their thereby these this thorough through
transformative typically ultimately uncharted uncovering underexplored underscore underscored
underscores underscoring understanding unexplored unlocking unparalleled unraveling unveil
unveiled unveiling unveils uphold upholding urging using utilized utilizes utilizing valuable
various varying verifies versatility wandering warranting were while within yielding
""".split())
