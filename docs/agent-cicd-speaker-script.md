# Speaker script: A controlled release path for AI agents

## Slide 1 — A controlled release path for AI agents

I want to explain a practical way to release an AI agent in a controlled manner.

The main point is that an agent is more than a piece of code. Its behaviour also depends on its instructions, the model, the tools it can use, the data it can reach, and the rules used to judge its answers. A normal build can tell us whether the code is valid. It cannot tell us whether the agent still behaves as intended.

The release path therefore has four parts. First, a developer makes a change. Second, the pipeline validates the files and the code. Third, the changed agent is deployed to a development environment and evaluated there. Finally, the same reviewed commit can be promoted to production after an approval.

This is not about removing people from the process. It is about giving reviewers better evidence. Instead of asking someone to trust that a prompt change is safe, the pipeline shows the responses produced by that exact version of the agent.

The phrase at the bottom is the key idea for the rest of the presentation: we release behaviour, not only code.

## Slide 2 — The repository is the source of truth

The process begins in source control.

Everything needed to describe the agent should be versioned together. This includes the runtime code, the instructions, the available tools, and the evaluation cases. It also includes the thresholds that decide whether a candidate is good enough to move forward.

Keeping these items together gives us a clear release package. A commit is not only a code change. It is a full description of the agent version that we intend to test.

This also reduces manual work. We should not have to copy a prompt from a document, configure a tool in a portal, and then hope that the production setup matches the test setup. Environment-specific values, such as endpoints and identities, can remain separate. The behaviour definition should remain in the repository.

This structure also helps when something goes wrong. We can identify which instruction, tool definition, model setting, or evaluation case belonged to a specific release. We can compare two commits and understand what changed.

The result is a simple contract: one commit represents one candidate. That candidate can be rebuilt and checked again.

## Slide 3 — A pull request creates a release candidate

When a developer opens a pull request, the pipeline starts with fast checks.

These checks cover normal software concerns. The code is linted. Unit tests are run. Configuration files are parsed. Dependencies and common security issues can also be checked. If one of these checks fails, there is no reason to deploy the agent.

When the basic checks pass, the pull-request commit is deployed to a development environment. This creates a real agent version. The pipeline does not evaluate a text file in isolation. It evaluates the agent as it will actually run, with its runtime, instructions, and allowed tools.

The pipeline then sends a fixed set of test requests to the agent. These requests cover important behaviour and known risks. For example, a test can check that the agent refuses an unauthorised write, asks for missing information, or does not invent data.

The final step is a merge gate. If the deployed candidate fails the required scores or produces an error, the pull request cannot be merged.

This is an important distinction. A green build only tells us that the software can run. The behaviour evaluation tells us whether this version should be released.

## Slide 4 — Evaluation produces evidence, not just a percentage

An evaluation report should be useful to a reviewer.

A single percentage is not enough. If a score is low, we need to know which request failed. We also need to see the response and the reason given by the evaluator. If the agent could not respond because of a service error, that should be shown separately from a quality failure.

The example on the left shows the kind of evidence that should be retained. We have the original test request and the exact response from the deployed candidate. In this case, the response refuses an unsafe action, explains what information is missing, confirms that no write was made, and includes a short joke because that is part of the current instruction.

The response is checked by different evaluators. Built-in evaluators can cover areas such as fluency and safety. A task evaluator checks the required behaviour for that test case. Custom evaluators cover rules that are specific to the organisation or to the current change.

For example, if the instruction was changed to require a brief joke, a custom evaluator should judge only whether a suitable joke is present. It should not hide that result inside a general quality score.

The report should show the response, the score, and the evaluator’s reason for every case. This makes the pull-request decision understandable and auditable.

## Slide 5 — Promote the same commit through controlled environments

After the pull request is approved and merged, the merged commit is checked again in the development environment.

This second check matters because the production candidate is now the commit on the main branch. We want evidence for that exact commit, not only for an earlier branch state.

When the checks pass, the pipeline reaches a production approval. A named reviewer can inspect the evaluation summary and the full report. The reviewer can see the agent responses, the custom rules, and any warnings before allowing the deployment to continue.

The production deployment then creates a new agent version from the same source commit.

Some values are expected to differ between development and production. Each environment can have its own identity, project endpoint, tool connection, and access policy. These differences should be declared as configuration.

The code, instructions, and evaluation cases should not be changed during promotion. If someone changes those items, it is a new candidate and it must go through the checks again.

This keeps the release path clear. We know what was reviewed, what was evaluated, who approved it, and which version reached production.

## Slide 6 — Production closes the loop

The process does not end when the agent reaches production.

Production gives us new evidence. We can inspect traces, errors, user feedback, slow responses, and cases where the agent was technically correct but not useful. These findings should feed back into the repository.

When a meaningful failure is found, we turn it into a stable evaluation case. The case should describe the input, the expected behaviour, and the relevant rule. This means the same problem can be checked automatically in future releases.

The team can then decide what needs to change. It may be the runtime code. It may be the instruction. It may be a tool definition, an access rule, or a model setting. The change goes through the same pull-request and evaluation path.

Over time, the evaluation set becomes a practical record of the risks and expectations that matter to the organisation.

The four control points on the right remain important throughout the loop: source control, repeatable tests, visible evidence, and named approval.

The final message is straightforward. An AI agent should be treated as a changing software system with measurable behaviour. The pipeline gives us a consistent way to make changes without losing oversight.
