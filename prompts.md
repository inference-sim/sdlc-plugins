CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1 $HOME/.local/share/claude/versions/2.1.38


curl -L -o ~/.claude/versions/claude-code-2.1.22 https://github.com/anthropics/claude-code/releases/download/v2.1.22/claude-code-darwin-arm64


Here's some additions to the /research-ideas plugin. Create a plan for fixes
1. Update README instructions on how to enable auto-update from marketplace
2. Instruct users on how to create a problem.md for a problem statement. If they don't know what a good problem statement is, they can use the superpower:branstorm plugin!
3. The summarize-problem-context should take in a variety of inputs. The user can provide requests for context summarization across many repos (including this one, and that should be enabled by default), remote github repos, papers that could be found online. These each source of context should be launched by a background explore agent that has websearch capabilities. These sources should be summarized according to the problem statement. Make sure that each source is launched in parallel background subagent sessions.
4. The UI should prompt users in terms of where the problem statement is, how the background should be generated (can also be entirely skipped or supply by user), then proceed to judge configuration (what models to use for judges, enable three by default), number of idea iterations
5. The UI should show a clean dashboard to track progress
6. Update patch version, update README, update CI/CD