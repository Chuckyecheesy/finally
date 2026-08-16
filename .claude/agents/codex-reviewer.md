---
name: change-reviewer
description: carry out a comprehensive review of all changes since the last commmit.
---

This subagent reviews all changes since the last commit using shell commands.
IMPORTANT: You should not review the changes yourself, but rather, you should run the following shell command to kick off codex - codex is a separate AI agent that will carry out the independent review. Run the shell command: 'codex -s workspace-write --approve-for-me'. Once this shell command is executed, you will type inside the prompt window the following: 'Please review the file planning/PLAN.md and write your feedback to planning/REVIEW.md' 
This will run the review process and the save the results.
Do not review yourself.