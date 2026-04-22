- add xxx to .md convert support
- context management, split huge matierals and generate seperately
- prompt templet
  - basic front and back
  - front back has answer and explanation
- tools
  - get similar cards
- prompt fine-tuning
  - question can be asked out of context
  - answer should short, something the learner should memorize, answer should not be ambiguous
  - questions should be "knowledge", should be important, should be useful
  - granularity should consider material length and card count

- explanation field in card back

- LLM-based editing/reviewing cards before adding to database
  - context reserving in the reviewing phase
  - edit/re-write front
  - edit/re-write back

- auto card counts

- other card types (card templates?)
  - cloze
  - holes in picture

- optimize bundle size because the cc cli is very big
  - try re-use user's cc?
  - download on-demand?

- generating progress interface
- add source file name as tag to cards
- when saved, reset attached files