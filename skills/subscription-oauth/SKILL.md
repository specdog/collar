---
name: subscription-oauth
description: "Use DAG Agent with your existing AI subscription — OAuth login, no API key."
version: 1.1.0
author: Collar Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  dag:
    tags: [oauth, subscription, login, setup, onboarding, chatgpt, qwen, nous, xai, grok, anthropic, gemini]
    trigger_on: [oauth, subscription, login, api-key, setup, api key, chatgpt, plus, pro, grok, supergrok, claude, gemini]
---

# OAuth Login (No API Key)

Have an AI subscription? Log in with OAuth — skip API keys entirely.

## Quick

ChatGPT Plus → dag auth add openai-codex
Qwen Plus/Pro → dag auth add qwen-oauth
Nous Portal → dag auth add nous
xAI SuperGrok → dag auth add xai-oauth
Anthropic Claude Pro → dag auth add anthropic --type oauth
Google Gemini → dag auth add gemini-oauth

After auth: dag model → pick provider → /reset if in session.

## Discovery

dag setup model — wizard offers OAuth providers. Or dag auth add <provider>.

## Headless

No browser: copy URL to phone, or ssh -L 8080:localhost:8080, or fallback to OpenRouter key.

## OpenAI Codex

dag auth add openai-codex
Needs ChatGPT Plus ($20/mo)+. Free=no.
Device code → chatgpt.com/device → token saved. 10min expiry.
Pitfalls: 401=re-auth. "No models"=dag model.
Verify: dag auth list → dag chat -q "test" --provider openai-codex

## Qwen

dag auth add qwen-oauth
Needs Qwen Plus/Pro (Alibaba Cloud/Tongyi).
Pitfalls: region-dependent. Provider is "qwen" not "qwen-oauth" in dag model. 401=re-auth.
Verify: dag auth list → dag chat -q "test" --provider qwen

## xAI Grok

dag auth add xai-oauth
Needs xAI SuperGrok or Premium+ subscription.
Browser login → authorize → token saved.
Pitfalls: 401=re-auth. OAuth also works for TTS (setup wizard detects it).
Verify: dag auth list → dag chat -q "test" --provider xai

## Nous

dag auth add nous
Needs Nous Portal account. Free tier OK.
Pitfalls: free tier limited models/rate. Email verify may be needed.
Verify: dag auth list → dag chat -q "test" --provider nous

## Anthropic (may be broken)

dag auth add anthropic --type oauth
Needs Claude Pro subscription.
⚠ Known issue: Anthropic blocks some OAuth clients (404 on token endpoint). If it fails, fallback to OpenRouter API key.
Verify: dag auth list → dag chat -q "test" --provider anthropic

## Google Gemini

dag auth add gemini-oauth
Needs Google One AI Premium or Gemini Advanced subscription.
⚠ May not work for auxiliary tasks (vision, compression). Main chat OK.
Pitfalls: provider is "gemini" not "gemini-oauth" in dag model.
Verify: dag auth list → dag chat -q "test" --provider gemini

## Rate Limits

OAuth = lower throughput than API-key. Fine for chat. Not for batch.
Fallback: OpenRouter (OPENROUTER_API_KEY) — one key, 200+ models, pay-per-token.

## Cmd

dag auth add openai-codex|qwen-oauth|xai-oauth|nous|anthropic|gemini-oauth
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
3. Ask: ChatGPT, Qwen, xAI, Nous, Claude, or Gemini?
4. dag auth add <match>
5. Wait browser auth.
6. dag auth list verify.
7. dag model set default.
8. /reset if in session.
9. dag chat -q "test" verify.
10. Warn rate limits if batch. Anthropic/Gemini may have known issues — mention fallback.
