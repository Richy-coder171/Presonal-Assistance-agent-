# AgentTalent.ai Upload Checklist

- [ ] Demo mode verified.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python -m compileall assistant_agent tests -q` passes.
- [ ] `AGENT_PROFILE.md` reviewed.
- [ ] Security, privacy, operations, and evaluation docs reviewed.
- [ ] Production env values set outside the repo.
- [ ] `TOKEN_ENCRYPTION_KEY` and `SESSION_SECRET` generated.
- [ ] `ADMIN_EMAIL` configured.
- [ ] Google OAuth redirect URI configured.
- [ ] Microsoft OAuth redirect URI configured.
- [ ] Write scopes left disabled unless the review requires approved write-action testing.
- [ ] Screenshots recorded with no real user secrets or private tokens visible.
