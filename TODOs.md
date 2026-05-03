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
- edit prompt tab

- sub agents for very long materails
- math equation tex display

- card limit should be input box

- how to use vector db?

- should support a code repository??

- beyond just creation, what should user do if he forget and don't understand a question

- formal model provider configuration interface

- markdown to html post processing?

- a fast way to add a single question using LLM

- auto card count mode

- if cannot be converted, fallback to plain text

- add a instruction prompt box

- LLM enhanced reviewing
  - question validation
  - question re-phrase
  - answer validation
  - answer re-phrase
  - explanation
  - re-write explanation
  - re-answer by LLLM

- add a mode to append raw materials (don't convert to markdown for the user)
- suppor append/drag folder/s

- re-generate card content should has a optional purpose