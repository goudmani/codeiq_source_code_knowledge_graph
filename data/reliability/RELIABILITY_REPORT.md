# Reliability report

Generated from 10 questions, 33 total live samples (adaptive 3-then-5 per question, early-stopped on unanimous agreement).

**PASS: 6 / FAIL: 0 / INCONCLUSIVE: 3 / ERROR: 1**

| Question | Verdict | Samples | Agreement | Tool-trace | Entity-overlap | Confidence-stable |
|---|---|---|---|---|---|---|
| q1: Which hook manages the app's authenticated session state, and where is it defined? | PASS | 3 | 1.00 | - | - | recovered from stdout, no fingerprint detail |
| q4: Which screen implements the Bookmarks feature, and what does it depend on for fetching bookmark data? | INCONCLUSIVE | 5 | 0.40 | - | - | recovered from stdout, no fingerprint detail |
| q5: What breaks if useSession changes its behavior -- who calls it directly? | PASS | 3 | 1.00 | - | - | recovered from stdout, no fingerprint detail |
| q6: Where is HashtagScreen defined? | PASS | 3 | 1.00 | - | - | recovered from stdout, no fingerprint detail |
| q13: What does the TabsNavigator component in src/Navigation.tsx render? | ERROR | - | - | - | - | Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01kpffev9cfjcrh0mbyrzgwycr` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 198321, Requested 10772. Please try again in 1h5m28.176s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}} |
| q15: What breaks if the useAgent hook changes its behavior -- who calls it directly? | PASS | 3 | 1.00 | 1.00 | 1.00 | 1.00 |
| q18: Which components or screens use the useAccountSwitcher hook? | INCONCLUSIVE | 5 | 0.40 | 1.00 | 0.40 | 1.00 |
| q20: Is there an internal storybook or developer showcase screen in the app? Where is it defined? | PASS | 3 | 1.00 | 1.00 | 1.00 | 1.00 |
| q24: Does the app have a reusable error boundary component? Where is it defined? | PASS | 3 | 1.00 | 1.00 | 1.00 | 1.00 |
| q30: What does the file src/view/com/post/Post.tsx depend on for opening the composer and for post-state caching? | INCONCLUSIVE | 5 | 0.40 | 1.00 | 0.60 | 0.80 |
