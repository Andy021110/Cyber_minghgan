# LongMemEval oracle full-500 Badcases

- 来源：`latest_longmemeval_oracle_full.json`
- 准则：score < 1
- 数量：**103** / 500（0分 89 · 半分 14）
- 总分对照：404.0/500 (avg 0.808)

## 分型统计

| type | n_bad | avg_score_among_bads | ret=0 | empty_hyp |
|------|------:|---------------------:|------:|----------:|
| abstention | 4 | 0.0 | 0 | 0 |
| knowledge-update | 10 | 0.1 | 0 | 0 |
| multi-session | 31 | 0.081 | 0 | 4 |
| single-session-assistant | 1 | 0.5 | 0 | 0 |
| single-session-preference | 17 | 0.118 | 1 | 0 |
| single-session-user | 3 | 0.167 | 0 | 0 |
| temporal-reasoning | 37 | 0.014 | 0 | 4 |

## 失败标签计数

- `judge_says_mismatch`: 43
- `temporal`: 37
- `multi_session`: 34
- `judge_parse_error`: 17
- `preference_rubric`: 17
- `knowledge_update`: 11
- `empty_answer`: 8
- `abs_leak_or_fail`: 4
- `no_retrieve`: 1

## 代表性例子（摘要）

### [single-session-preference] `8a2466db` score=0.0 ret=0
- Q: Can you recommend some resources where I can learn more about video editing?
- Gold: The user would prefer responses that suggest resources specifically tailored to Adobe Premiere Pro, especially those that delve into its advanced settings. They might not prefer general video editing resources or resources related to other video editing software.
- Hyp: This is a general knowledge question, so let me provide some widely recognized resources for learning video editing:

**Free Courses & Tutorials**
- **YouTube channels**: Peter McKinnon, Premiere Gal, Casey Faris (DaVinci Resolve), and Film Riot offer excellent free tutorials for...
- Judge: WRONG — The hypothesis provides general video editing resources across multiple software and skill levels, not specifically tailored to Adobe Premiere Pro's advanced settings as the user prefers.
- tags: no_retrieve, preference_rubric

### [single-session-preference] `0edc2aef` score=0.0 ret=3
- Q: Can you suggest a hotel for my upcoming trip to Miami?
- Gold: The user would prefer suggestions of hotels in Miami that offer great views, possibly of the ocean or the city skyline, and have unique features such as a rooftop pool or a hot tub on the balcony. They may not prefer suggestions of basic or budget hotels without these features.
- Hyp: I searched through our past conversations, but I wasn't able to find anything about a Miami trip — all of our previous hotel discussions were focused on **Seattle**. Because of that, I don't have enough context from your history to make a personalized Miami recommendation.

Here'...
- Judge: None — None
- tags: judge_parse_error, preference_rubric

### [temporal-reasoning] `a3838d2b` score=0.0 ret=4
- Q: How many charity events did I participate in before the 'Run for the Cure' event?
- Gold: 4
- Hyp: Based on the evidence gathered from your memory, I can identify **two charity events** you participated in before the "Run for the Cure" event (October 15th):

1. **Charity Golf Tournament** — attended on **July 17th**, which you described as "a blast playing with colleagues."
2....
- Judge: WRONG — The hypothesis incorrectly states 2 charity events before 'Run for the Cure', but the correct number is 4.
- tags: judge_says_mismatch, temporal

### [temporal-reasoning] `982b5123` score=0.0 ret=1
- Q: How many months ago did I book the Airbnb in San Francisco?
- Gold: Five months ago
- Hyp: Based on the retrieved memory, I don't have enough information to answer that question precisely. The relevant conversations (from May 27, 2023) show you were planning a trip to San Francisco and mentioned staying at an Airbnb in Haight-Ashbury, as well as referencing a past stay...
- Judge: WRONG — The hypothesis states the question cannot be answered due to missing information, while the gold answer provides a specific number of months ago, so they do not match.
- tags: judge_says_mismatch, temporal

### [multi-session] `0a995998` score=0.0 ret=2
- Q: How many items of clothing do I need to pick up or return from a store?
- Gold: 3
- Hyp: Based on your past conversations, you have **2 clothing items** to pick up:

1. **A new pair of boots from Zara** — You mentioned on February 15 that you exchanged a pair you bought on 2/5 and still needed to pick up the replacement pair.
2. **A navy blue blazer from dry cleaning...
- Judge: WRONG — The hypothesis states 2 items, but the gold answer is 3, so the answer does not match.
- tags: judge_says_mismatch, multi_session

### [multi-session] `6d550036` score=0.0 ret=4
- Q: How many projects have I led or am currently leading?
- Gold: 2
- Hyp: Based on the available information from our conversations, here's what I can tell you:

**Projects you've led: 1**

- **Marketing Research class project** — You led the data analysis team and conducted a comprehensive market analysis for a new product launch.

**Regarding current...
- Judge: WRONG — Hypothesis states 1 project led, which contradicts the gold answer of 2.
- tags: multi_session

### [knowledge-update] `852ce960` score=0.0 ret=1
- Q: What was the amount I was pre-approved for when I got my mortgage from Wells Fargo?
- Gold: $400,000
- Hyp: Based on your past conversations, there's an inconsistency in what you've shared. Here's what the records show:

- **August 11, 2023**: You mentioned being pre-approved for **$350,000** from Wells Fargo for a $325,000 home purchase.
- **November 30, 2023**: You referenced being p...
- Judge: WRONG — The hypothesis does not state the gold answer of $400,000 but instead presents an inconsistency with two amounts and cannot confirm the correct one.
- tags: judge_says_mismatch, knowledge_update

### [knowledge-update] `89941a93` score=0.0 ret=1
- Q: How many bikes do I currently own?
- Gold: 4
- Hyp: Based on your conversation history, you currently own **three bikes**:

1. **Road bike** – used for long weekend rides and your upcoming century ride
2. **Mountain bike** – used for trail rides
3. **Commuter bike** – used for daily commutes

This was mentioned when you said, *"I'...
- Judge: WRONG — The hypothesis says three bikes but the gold answer is four.
- tags: knowledge_update

### [abstention] `88432d0a_abs` score=0.0 ret=3
- Q: How many times did I bake egg tarts in the past two weeks?
- Gold: The information provided is not enough. You did not mention baking egg tarts.
- Hyp: Based on the available memory records, I couldn't find any mention of you baking egg tarts — not in the past two weeks, nor at any other time in the stored conversations. The baking-related episodes do show you've been quite active with things like cookies, chocolate cake, whole ...
- Judge: None — None
- tags: judge_parse_error, abs_leak_or_fail, multi_session

### [abstention] `edced276_abs` score=0.0 ret=4
- Q: How many days did I spend in total traveling in Hawaii and in Seattle?
- Gold: The information provided is not enough. You mentioned traveling for 10 days in Hawaii but did not mention abything about the trip to Seattle.
- Hyp: Based on the information I found in your memories, here's what I can tell you:

- **Hawaii:** You took a family island-hopping trip to Hawaii that lasted **10 days**. You mentioned that with your family, "we had to plan everything out for the 10-day so far in advance."

- **Seatt...
- Judge: None — None
- tags: judge_parse_error, abs_leak_or_fail, multi_session

### [single-session-user] `51a45a95` score=0.0 ret=2
- Q: Where did I redeem a $5 coupon on coffee creamer?
- Gold: Target
- Hyp: Based on the available memory, you mentioned redeeming a $5 coupon on coffee creamer "last Sunday" (around May 21, 2023), and that it was a surprise from your email inbox. However, you didn't explicitly state **which store** you redeemed it at. While the surrounding conversation ...
- Judge: WRONG — The hypothesis incorrectly asserts that no store is mentioned, while the gold answer specifies Target as the redemption location.
- tags: judge_says_mismatch

### [single-session-user] `ec81a493` score=0.0 ret=2
- Q: How many copies of my favorite artist's debut album were released worldwide?
- Gold: 500
- Hyp: Based on our past conversations, I don't have enough information to answer this question. Here's what I know:

- You've mentioned your **favorite artist** several times, but you never actually named who that artist is, so I can't identify them or look up their debut album.
- You ...
- Judge: WRONG — The hypothesis does not provide the gold answer of 500 copies; instead it states it cannot answer and mentions a separate 500 figure for a poster.
- tags: judge_says_mismatch

### [single-session-assistant] `778164c6` score=0.5 ret=1
- Q: I was looking back at our previous conversation about Caribbean dishes and I was wondering, what was the name of that Jamaican dish you recommended I try with snapper that has fruit in it?
- Gold: Grilled Snapper with Mango Salsa
- Hyp: Based on our previous conversation, the Jamaican dish I recommended you try was **Escovitch Fish** — fried snapper topped with a spicy pickled vegetable sauce (carrots, onions, bell peppers, vinegar).

However, Escovitch Fish doesn't actually feature fruit — so you may be thinkin...
- Judge: PARTIAL — The hypothesis includes 'Grilled Snapper with Mango Salsa' as a possible answer, which matches the gold, but it is not given as the primary answer and is preceded by an incorrect suggestion; thus it partially captures the key fact.
- tags: judge_says_mismatch
