---
name: subscription-oauth
description: "Use DAG Agent with your existing AI subscription — OAuth login, no API key."
version: 1.0.0
author: Collar Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  dag:
    tags: [oauth, subscription, login, setup, onboarding, chatgpt, qwen, nous]
    trigger_on: [oauth, subscription, login, api-key, setup, api key, chatgpt, plus, pro]
---

# OAuth Login (No API Key)

Have ChatGPT Plus, Qwen Pro, or Nous? Log in with OAuth — skip API keys entirely.

## Quick

ChatGPT Plus → dag auth add openai-codex → dag model → /reset
Qwen Plus → dag auth add qwen-oauth → dag model → /reset
Nous → dag auth add nous → dag model → /reset

## Discovery

dag setup model — wizard offers OAuth providers. Or dag auth add <provider>.

## Headless

No browser: copy URL to phone, or ssh -L 8080:localhost:8080, or fallback to OpenRouter key.

## OpenAI

dag auth add openai-codex
Needs ChatGPT Plus ($20/mo)+. Free=no.
Device code → chatgpt.com/device → token saved. 10min expiry.
Pitfalls: 401=re-auth. "No models"=dag model.
Verify: dag auth list → dag chat -q "hello" --provider openai-codex

## Qwen

dag auth add qwen-oauth
Needs Qwen Plus/Pro. Region-dependent.
Pitfalls: provider is "qwen" not "qwen-oauth" in dag model. 401=re-auth.
Verify: dag auth list → dag chat -q "hello" --provider qwen

## Nous

dag auth add nous
Needs Nous Portal account. Free tier OK.
Pitfalls: free tier limited. Email verify may be needed.
Verify: dag auth list → dag chat -q "hello" --provider nous

## Rate

OAuth limited vs API-key. Fine for chat, not batch. Fallback: OpenRouter.

## Cmd

dag auth add openai-codex|qwen-oauth|nous
dag auth list
dag auth remove PROVIDER
dag auth reset PROVIDER
dag model
dag setup model

## Files

~/.dag/auth.json — OAuth tokens
~/.dag/config.yaml — model.provider / model.default

## Steps

1. New? dag setup model. Existing? dag auth add.
2. Headless? copy-URL or OpenRouter fallback.
3. Ask: ChatGPT, Qwen, or Nous?
4. dag auth add <match>
5. Wait browser auth.
6. dag auth list verify.
7. dag model set default.
8. /reset if in session.
9. dag chat -q "hello" test.
10. Warn rate limits if batch use.
