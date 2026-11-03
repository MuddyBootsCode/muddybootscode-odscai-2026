# Ontology review and verification

The user approved four additions: distinguish acknowledgment from verification;
record domain authority and actionable open questions; fail when Git comparison
is unavailable; test installation and lifecycle in gradgraph-auth-platform.

Extend the existing stdlib checker and Codex adapter. Keep exit status as the
change-review gate and add explicit review and verification fields. Test execution
is an explicit user/agent-selected command, never automatic execution of Markdown.
Record its output, exit, rule and repository snapshot. Later edits invalidate proof.
A passing command is evidence for the selected check, not proof the check is adequate.
Domain confirmation is independent of both review and executable verification.

Approaches: prose-only guidance cannot distinguish runtime outcomes; automatically
running free-form gate annotations is ambiguous. Use an explicit verification CLI
and retain existing gate annotations for discovery. This is an implementation
choice within the behavior approved in chat.

Preserve existing Claude behavior and schema consumers through additive fields.
Use narrow GradGraph skills authorization rules as the local integration example;
never change production authorization behavior to demonstrate a failure in the
working checkout. Use a disposable copy for deliberate violations. Native hook
trust must be reviewed through supported UI, not bypassed. Record any unobserved
installation or live-session gate honestly.
