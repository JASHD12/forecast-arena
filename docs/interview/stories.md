# Five stories in STAR form (T393)

Each story is true and comes from the repository: the decision records (`docs/project/DECISIONS.md`), the result files and the
generated [numbers.md](numbers.md), which holds every figure quoted here. Each ends with what I would do differently.

## 1. The AI did not win where I expected it to (weather)

**Situation.** The project asks when an LLM agent beats a classical model. I expected the agent to win somewhere numeric. **Task.** Find out
where, before the record could flatter me. **Action.** I pre-registered the comparison, scored every topic separately with day-block
intervals, and read the weather code to see why. The ML model turns the DWD forecast into a probability with a fixed error model; the language
models only get the same forecast as numbers and are told to start from the base rate. **Result.** On weather the ML model scores 0.0829
against 0.1283 for the AI agent and 0.1807 for the AI with data; on Wikipedia attention the agent is level with it (0.0785 against 0.0884). It is
too early to call, and I said so on the page. **Differently.** I would have given the agent an error-model tool from day one, and I would fit the
weather error model on stored forecast errors instead of fixed spreads (that is the next planned task, gated on 60 days of data).

## 2. A whole day's batch was lost, and the fix was to measure first

**Situation.** On 24 November the morning batch was never written: GitHub's scheduler had fired only about two of nine slots a day and the first
run on that day started at 09:52, after the 09:30 UTC lock. **Task.** Never write a forecast after its lock, and stop it happening again.
**Action.** The ledger refuses a late forecast (rule I1), so nothing was backdated; I recorded the miss, opened an incident, collected the
start times of the previous days, and raised the schedule from 9 to 42 slots while keeping runs idempotent. I also wrote down that the reliable fix
is an external trigger, which needs the owner's account. **Result.** The check that a morning batch exists now fails loudly, and the evidence is
in the decision record. **Differently.** I trusted a cron schedule to be on time; I would have measured its start times in the first week and
designed for the late case from the start.

## 3. The committee that answered 37 of 90 questions

**Situation.** I added a committee of specialist agents over the A2A protocol and pre-registered a test against one agent with skills.
**Task.** Run it once and report whatever happened. **Action.** The first run answered only 37 of 90 questions: the skeptic's reply failed to
parse because 119 of 316 calls ended at a 300-token output cap. My quorum rule recorded each as a skip with its reason instead of filling in a
number, which is how the cause became visible. I fixed it as a new version, `committee-r2`, pre-registered again, not by patching r1.
**Result.** Version r2 answered 87 of 90 questions and still did not beat one agent with skills (Brier difference +0.0060, interval
[-0.0036, +0.0152]) at about 1.4 times the cost. **Differently.** I should have run a ten-question dry run for format failures before spending on
the 90.

## 4. The fine-tune that beat its untuned self and still lost to the base rate

**Situation.** I fine-tuned a 1.5B open model (QLoRA) on replayed questions. **Task.** Decide, with numbers, whether it was worth running.
**Action.** Pre-registered the test on frozen questions it never saw, with the untuned model, the base rate and `ml` as references.
**Result.** It beat its untuned self (-0.0090 [-0.0148, -0.0028] on the October questions) and was worse than the base rate (+0.0145
[+0.0021, +0.0262]). The result is published with its card; the model is not in the headline. **Differently.** I would have checked the base rate
on the training questions before training, because a task this close to a coin flip has little for a small model to learn.

## 5. The token cap that the Status page showed wrongly

**Situation.** The daily token cap lived in three places: the code default, the workflows and the specification. **Task.** Make the Status page
tell the truth. **Action.** The page read the code default (400,000) while the workflows enforced 300,000, so it showed a share of the cap that was
too low. I aligned the default, then added a test that fails if the code default, the three workflows and the specification ever disagree.
**Result.** One number, enforced by a test. **Differently.** I would have written the consistency test when I introduced the second copy of the
number, not after it drifted.
