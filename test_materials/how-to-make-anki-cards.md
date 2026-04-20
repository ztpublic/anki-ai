Reviewing in Anki is easy: all you have to do is answer the question and press a button to indicate how well you remembered it. Creating the cards to review, however, is a complex discipline of its own that’s both an art and a science, and how well you do at designing your cards can make the difference between easy study sessions resulting in effective learning and frustrating ones resulting in mediocre learning. Card design is thus the most fundamental skill of spaced-repetition use, and it’s worth spending some time learning how to do it well.

Throughout the next couple of posts on creating cards for spaced-repetition systems, I’ll be frequently referencing SuperMemo’s [Twenty Rules of Formulating Knowledge](http://super-memory.com/articles/20rules.htm). It would be hard to overstate the importance and influence of this document in the spaced-repetition community, and if you have not read it, you should do so now, or at least put it on your reading list. As a matter of fact, you should read it twice, consider memorizing the principles, and keep returning to and rereading it as you learn more about spaced repetition – it’s one of those resources you learn more from every time you read it.

## The importance of asking the right questions

An SRS does a fantastic job of helping you remember the information you put into it. However, it is a strongly garbage-in, garbage-out tool: if you put in material that isn’t useful or doesn’t test the things you want to know, you’ll remember it, but it won’t help you at all; you’ll just be wasting your time doing reviews. This poses a challenge for users, because seemingly small variations in how you ask a question can push it into not testing the thing you intended it to. The SRS is rather like the proverbial genie: describe what you want to get in the wrong way, and the genie will interpret your wish in the most ridiculous way possible and you’ll learn something that’s of no practical use. For instance, I recently found a card with an interval of several years in my own collection, asking what option to the `cp` (copy) Unix command makes it ask for confirmation before overwriting existing files. I easily and correctly answered, “ `cp -i`,” but as I gave that answer, I realized that I had completely forgotten that `cp` *had* such an option in the first place, so I would never have thought to use the option when it would have been useful, and this information was pretty much worthless to me. In other cases, you could end up memorizing a grammatical error on your card, or a learned response to a prompt which you would never encounter in real life.

To put it another way, SRS questions are prone to *overfitting*. [Overfitting](https://en.wikipedia.org/wiki/Overfitting), in statistical modeling and machine learning, occurs when a model gets “too good” at predicting the data you train it on – it starts to treat random noise present in the training data as a meaningful source of predictions. Of course, random noise does not represent any meaningful relationship that would be useful in predicting new information. Thus, overfitting improves the model’s accuracy rate on the training data but reduces it when it’s applied to new data, i.e., a real-world scenario. In a spaced-repetition context, because the SRS is so good at helping you learn things efficiently, it will optimize your memory of just about anything, but if you don’t phrase your question correctly, it will help you remember irrelevant information or random noise, rather than the information you actually wanted to know.

To avoid overfitting, the number-one rule when adding cards is this: every time you come across something you think you’d like to remember, **identify exactly what you want to know**, and be as precise about it as possible. Then, and only then, create one or more cards that ask about exactly that and nothing else. Doing this is more difficult and makes your initial learning process longer, compared to just dumping the information onto a flashcard, but it works much better! As a bonus, this process helps you understand and memorize the information, even before you start reviewing the cards: you’re forced to reflect on what exactly the information means to you, when you would need to use it, and how it relates to things you already know. This is an accidental form of the memory technique known as *elaborative encoding*, which has been consistently found to be one of the most effective ways to learn things – and you’re getting it for free while doing something you already needed to do to create your flashcards!

The remainder of this post will lay out some rules to help you ask the right questions on your cards. While I’ve made up one or two of the examples, the vast majority of them are real cards that came out of my personal collection today, just to demonstrate that most every spaced-repetition user has some of these skeletons in his closet (many of them are on my older cards, but several are much newer).

## Questions should ask exactly one thing

Rule #4 of the [Twenty Rules](http://super-memory.com/articles/20rules.htm) calls this the *Minimum Information Principle*: cards should never ask about more than one thing (techies might say that the card should be *atomic*). Violations of this rule may take obvious form, like literally asking two questions. However, most often they involve extremely general questions with a lot of content on the answer side:

> Q: Give a description of the Python programming language.  
> A: Python is a high-level, interpreted, multi-paradigm programming language written by Guido von Rossum and maintained by the Python Foundation. It is often used for system administration, data analysis, and rapid prototyping, and has been consistently named among the five most popular languages in recent years.

This is a terrible card! Not that you shouldn’t want to know anything about Python, or that any of the information in it is explained poorly, but there is just far too much information. Unless you want to literally memorize the text of the answer by rote, you will never be able to correctly give all the information in it as an answer to that vague prompt. If you forget any part of the question, you’ll either have to fail it (thus dooming the card to come back practically every day since you can never satisfactorily learn all of it) or say you remembered it well when you didn’t. We could easily split this into a dozen questions, e.g.:

> Q: Who designed the Python programming language?  
> A: Guido von Rossum.

> Q: What group maintains the Python programming language?  
> A: The Python Foundation.

> Q: Since 2015, Python has been ranked among the \[…number\] most popular programming languages.  
> A: 5

Et cetera.

It’s also worth pointing out there’s likely information in that initial “description” that we didn’t want to know in the first place and shouldn’t waste our time trying to learn. Splitting out what we’re learning into questions is a fantastic opportunity to decide what we need to remember so we can focus our efforts on the information that will be most valuable. Every piece of information you learn consumes study time that you could be using to learn other information. Choose wisely.

## Questions should permit exactly one answer

For efficient review, it must be immediately obvious both what is being asked and what single response will count as the correct answer; your thought process and your answer must be the same every time you review, in meaning if not in exact wording. This may seem straightforward, but most beginners frequently create cards that violate one or both of these rules. Heck, even experts do it from time to time. We can violate this rule in a wide variety of ways; let’s take a look at three common ones.

### Allowing correct but irrelevant answers

Here’s a cloze deletion from my AP US History deck (9 years ago now!). In my notation for cloze deletions, the bit in {curly braces} shows up as a `[...]` on the front of the card, asking you to fill in the blank; the whole sentence then shows up on the back.

> The Articles of Confederation had no power to regulate {commerce}.

This is true, and an important point (the lack of regulation of commerce was an important problem that helped drive the creation of the U.S. Constitution, which followed the Articles). However, there are a practically infinite number of other correct answers we could give! The Articles of Confederation also had no power to regulate religious observances, taxation, bear hunting, the behavior of the British monarch, or the hours your neighbor can play the drums with her windows open. Obviously, some of these answers are more plausible than others, but the fact remains I could reasonably give an answer that was *correct* but not the answer on the back of the card.

If that happens during review, it’s unclear what I should do. I could fail the card, which seems wrong because I gave a correct answer. Or I could pass the card, which seems wrong because there’s no evidence that I remembered the piece of information I was trying to retain by making this card. Either way, I am not effectively reviewing the piece of information I set out to learn; I’m instead forcing myself to memorize, in addition to the actual answer, *what this card is asking me*. That means I’m effectively asking about two things and making it much harder to remember the card, for no benefit – in real life, knowing what one of my Anki cards was supposed to be asking is useless information.

The correct response, when you encounter this situation during review – and you will – is to stop reviewing for a moment and rewrite the card. We could do this in numerous ways, but here’s one possibility:

> Economic and trade relations between states were difficult under the Articles of Confederation because the Articles granted no power to {regulate commerce}.

Of course, I could still come up with silly answers if I wanted to be contrary (I recommend being contrary – it’s fun). But, when reading the question in good faith, I can now be reasonably confident that if I don’t promptly remember the answer I intended, that means I’ve forgotten it.

### Falling into the “example” trap

Beginners often write questions like this one:

> Q: What’s an example of a non-combinatorial circuit?  
> A: Memory.

This is merely a special case of “allowing correct but irrelevant answers,” but I’ve seen it so frequently I want to call attention to it in particular. We have the same problem as before: not only do I have to remember that memory is a non-combinatorial circuit (the actual piece of information I wanted to know), I also have to remember that the specific example of a non-combinatorial circuit this card wants me to give is “memory”. An even worse version is “Give some examples of non-combinatorial circuits.” With this version, you can give different answers every time you see the card, including ones that aren’t on the card, and still have them be kind-of, sort-of, maybe correct!

Here’s another example. I perpetrated this one just a few days ago:

> Q: OutSystems: Give an example of something you might use an input parameter for.  
> A: In an edit screen, you would need to pass in the item to edit.

Fortunately, this question is trivial to recast into a useful form, once we’ve recognized that it’s problematic:

> Q: OutSystems: How would you use an input parameter on an edit screen?  
> A: To pass in the item you need to edit.

However, the word *example* doesn’t in itself mean you’re doing something wrong; examples on your cards are fantastic when used correctly, like in the following question:

> Asking why cats are unable to taste sweetness and humans are is an example of {functionalist} psychology.

Similarly, returning to the circuit question, we could write:

> Memory is an example of a {non-combinatorial} circuit.

In essence, we’ve inverted the example. This kind of question is more targeted and easier to answer and also tends to be more useful knowledge. In the real world, we’re rarely called upon to offer examples of a textbook term, but we often benefit from being able to recognize that something is an example of that idea. And chances are, if you learn the idea well enough to easily answer questions of this form, you won’t have any trouble offering some examples of it if you need to.

**Note**: The effectiveness of the two questions immediately above depends in great part on how complex your own taxonomy of those subjects is. Considering the memory question, I know relatively little about circuits, so I’m unlikely to get confused about what property of the memory circuit I’m being asked about. If I designed electronics for a living, on the other hand, I would likely need to rewrite that card with a hint or some additional context to be sure I knew which answer it was seeking. This is one of the many reasons that cards someone else makes will seldom be as effective as cards you make yourself: you’re the only one who knows what cues will get you the best results.

### Allowing multiple interpretations of a question

In this type of bad question, the creator didn’t clearly identify what they were trying to remember and consequently produced a vague question.

> APUSH: Americans moving to Texas \[when it was under Mexican control\] {did not adopt the ways of the region and remained Americans at heart}.

Is this the *only* thing I might have wanted to remember about Americans moving to Texas? Really? Now, no matter how bad this question is, I might be able to learn the answer (in fact, I have a nearly perfect, straight-3’s review history on this card), but the prompt is so vague that the only thing I’ve learned is “what to fill in the blank when I’m asked about Americans moving to Texas,” which is of little value in the real world.

> Q: Why is the Earth’s rotation slowing down?  
> A: Tidal deceleration.

This one’s a bit more subtle, but still problematic. The issue here is that the desired level of detail is unclear. Is it asking for the term that describes this phenomenon? (Is there even such a term? We wouldn’t know from the question.) Or did it want an explanation of the forces involved in tidal deceleration?

Here’s a better version:

> Q: What gravitational effect is causing the Earth’s rotation to slow over time?  
> A: Tidal deceleration.

If we didn’t know what tidal deceleration was, we’d also want to add a separate card, or maybe even several cards, explaining that process. That’s true even if we didn’t think we particularly wanted to know what tidal deceleration was. We don’t have a choice here: we *have* to know what tidal deceleration is for this card to be meaningful information. Even if we’re just trying to pass an exam which includes this exact question, the card will be much, much easier to remember when we know what it means. This is [Rule #1](http://super-memory.com/articles/20rules.htm): *Do not learn if you do not understand.*

Another important point is that having these cards may not remind us that Earth’s rotation *is* slowing down (see my anecdote about `cp -i` at the beginning of the post). Maybe we don’t care to recall that piece of information, and it would suffice to remember why it is, when we encounter a reference to the fact that it is. But if we do want to remember that it’s happening, we might also want to add a card to remind us, referencing the context in which we think we want to remember this information. For instance, maybe we care that the earth’s rotation is slowing down because it means [leap seconds](https://en.wikipedia.org/wiki/Leap_second) are needed to keep our calendar in sync with the day/night cycle:

> Q: Why are leap seconds periodically added to UTC time?  
> A: Because the earth’s rotation is slowing over time, causing UTC to drift out of alignment with the sun.

In any case, as always, we have to take a moment to consider what we want to know in order to ask the right questions and get the information encoded in a useful way.

## Questions should not ask you to enumerate things

When you find a list of items in your reading, it’s often tempting to create a card asking what the members of the list are. Rules #9-10 of the [Twenty Rules](http://super-memory.com/articles/20rules.htm) call these *sets* (or *enumerations*, if they go in a specific order), and explain that they’re some of the most difficult and frustrating cards, so we want to avoid them when possible.

Usually people create sets because they don’t realize sets are problematic or because they seem like the most obvious thing to learn, rather than because the set is actually what they want to know. In fact, being able to name all examples or parts of something is rarely helpful. A nasty illusion may make it appear to be, however. Consider the internal combustion engine, a classic example of a complex machine in many ways defined by its many parts. Someone who can name all the parts of the ICE will seem to have a good understanding of it. But this is an effect, rather than a cause. If you can name all the parts of the ICE but don’t know what they do, you still understand nothing at all about how it works. In contrast, if you know what all the parts do and how they relate to each other, you will easily be able to visualize the engine layout or work your way through the parts by function and name and describe each of them, regardless of whether you sat down and learned to recite them in order.

Of course, once in a while it really is helpful to know a set of things. In this case, you can improve your performance markedly by (a) learning and fully understanding each individual member of the set through separate cards; and (b) ordering the set into an enumeration and developing a mnemonic device such as an acronym for the order. (I like to keep close to the minimum information principle by creating two cards for part (b), one asking what my mnemonic is and the other asking me to use the mnemonic to produce the answer.) The [Twenty Rules](http://super-memory.com/articles/20rules.htm) has a good example of using this approach to learn the countries in the EU (rule #9), although it doesn’t include a mnemonic. But before you learn a set, even in an effective way, spend some time reflecting on whether it’s truly helpful.

Memorizing verbatim texts like poems or speeches is a special case of enumerations. In this case, overlapping cloze deletions are helpful, testing one line per card in a way that leads you to eventually recite every line in its context. My popular Anki add-on [LPCG](https://ankiweb.net/shared/info/2084557901) (Lyrics/Poetry Cloze Generator) can help you create cards from such texts.

## Questions should not ask for yes or no answers

Perhaps curiously, I find that questions whose answer is “yes” or “no” are harder to remember than questions that contain more information. They also tend to be less useful. If you create and learn cards that ask deeper questions, you’ll likely still be able to give the correct “yes” or “no” but also know additional information about why this is the case.

Here’s an example from my computer-hardware-design deck:

> Q: Is segmentation used on modern processors?  
> A: No, it was removed in the x86-64 platform.

Interestingly, you can see that I actually included the information needed to produce a better question in the answer. The answer is a terrible place for this kind of information, though: you’re never asked to actively recall it and you look at it for a fraction of the time you look at the question, so you’re unlikely to ever memorize it. Instead, we can rewrite the card:

> Segmentation was common on older processors but was removed starting with the {x86-64} platform.

Notice that by learning this fact (in which processor platform was segmentation removed?), we are still aware that segmentation is no longer used in the most modern processors, but we also know exactly when it was removed and what sorts of processors we might expect to find it in (provided we know something about processors, which I don’t expect you to!).

We might also consider creating a card, in addition to or instead of the above card, asking *why* segmentation was removed in the x86-64 platform. It all depends on what exactly we want to know, but *why* questions are usually valuable additions.

All this said, I do still find myself writing yes/no questions on occasion, especially when I’m in the early stages of learning a topic. Sometimes you don’t know the *why* yet, and it’s better at the moment that you simply learn that something is or isn’t, rather than go look up and learn a bunch of details just to be able to improve one flashcard. Perhaps later, you’ll have the additional understanding to rewrite the card.

That brings up an important point: questions are not set in stone. You’ll often miss potential problems with your new questions until you start reviewing them, and still other times you’ll learn a card and realize weeks or months later after reading a completely different resource that you were missing some important context or your initial understanding was flat-out wrong. You should make liberal use of the edit button while reviewing (in Anki, press `e` to edit the current card, and Escape when you’re done). If you spot a problem with a card that you can’t fix right away – maybe you’re reviewing on your phone and you need to look something up in a book at home to fix it up – use the “mark” function, which will add the tag “marked” to your card. When you have a few free moments, and before you forget what the problem was – I like to do this once a week or so – search for `tag:marked` in the browser and edit the cards appropriately, then unmark them again.

## Questions should be context-free

*Context-free* here is meant in the sense of a [context-free grammar](https://en.wikipedia.org/wiki/Context-free_grammar), that is, a grammar within which the correct interpretation of any statement is independent of its surroundings. Your questions, in other words, should be 100% comprehensible without any surrounding context; if you were to find one written on a slip of paper that somebody dropped in the street, you should be able to understand exactly what the question is asking. This design imperative takes two main forms.

**(1) The topic or context should be stated at the beginning or near the beginning of the question,** to prime your memory to retrieve the right kind of information and to facilitate reviewing cards from different subjects intermixed, which many people believe improves creativity. For instance, in several of my questions above, you saw qualifiers at the start of the question like `OutSystems:` or `APUSH:`. A word describing the topic worked into the sentence can work, too, although [Rule #16](http://super-memory.com/articles/20rules.htm) does recommend prefixes so you can be sure your brain gets started correctly.

If you don’t do this, you will often find yourself interpreting the question incorrectly – even if the question was clear in the context in which you were writing it, when you see it in the context of your reviews, it may not be so obvious. In fact, even if you *don’t* intermix questions from different disciplines, it’s possible to get confused. For example, I’ve long since lost count of the number of times I’ve given an answer in Latin to a card asking about German or English or my shorthand language, even when my last 30 cards had been in German!

My collection is full of thousands of cards that don’t have good context cues, and it will likely be years before I notice and fix all of the problem ones. Do yourself a favor and get in the habit right away. Even if you’re only studying, say, organic chemistry right now, ensure your questions can be comprehended within the context of a broader body of knowledge.

**(2) The question should not be built around a particular source.** It’s okay to *cite* your sources on your cards (actually, it’s a fantastic idea to reference sources in one way or another, because sooner or later you’re going to have doubts about the veracity of some card, or simply want to find more information about the topic). However, questions like this one are to be avoided:

> Statistics: One of the major focuses of our book’s introduction is that it is useful to measure {what you don’t know, or the uncertainty you have}.

First of all, this violates principle 1, since it just refers to “our book.” I happen to know which textbook it refers to at the moment, but at a different time I might not! But as for principle 2, I will never go, “Hey, what did the introduction of that statistics textbook I used my junior year of college focus on?” The premise of this question – describing what the textbook says – simply is not useful, and the information I’m learning from this card won’t be relevant in real life.

Hopefully, having read this article through this far, you’ve started to internalize the “What do I want to know?” mindset and this question just looks bad to you. I know it does to me.

Not to leave an exercise for the reader, how about this version:

> Statistics is not only about describing what you know but also about putting it in the context of {what you still don’t know}.

Be careful not to confuse this prohibition with a very useful pattern, namely that of asking what particular authors think about a topic, or qualifying information by saying that so-and-so said it. This other pattern uses the source information entirely differently: rather than making the question *about* the author’s book, it asks about the idea *in* the book while explaining where it came from. For example:

> Q: Why, according to Cal Newport, are discoveries often made by multiple people at the same time?  
> A: These things are part of the “adjacent possible” and were thus particularly easy to discover.

This becomes an especially valuable pattern once you get past the basic textbook knowledge and how-to rules in a field, where agreement can no longer be taken for granted. You don’t want to memorize opinions or nascent theories as facts!

## Conclusion

I hope these rules are helpful to you. Most spaced-repetition beginners vastly underestimate the importance of carefully worded questions, and I have yet to see anybody write about common issues in this level of detail. The rules are drawn from my own experience, but I’m the first to admit that I don’t know everything about writing cards; if anything, the longer I spend studying, the more things I realize I don’t understand! I would be interested to know if others have different experiences or have identified additional rules in the same vein.

Of course, rules are made to be broken, especially once you gain more experience, but if you start out by seeking to follow these, you’ll be kept out of many common traps that make spaced repetition less effective than it could or should be for many.