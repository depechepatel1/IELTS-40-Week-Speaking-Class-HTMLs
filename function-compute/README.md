# IELTS AI Correction — Function Compute

Aliyun Function Compute endpoint backing the "Correct with AI" button in the interactive IELTS HTMLs.
Calls Zhipu's latest free GLM model with a minimum-correction system prompt.

## Local development

```bash
cd function-compute
ZHIPU_API_KEY=test-key node --test test/      # all tests pass without network access
```

## One-time setup

1. Install Serverless Devs globally:

   ```bash
   npm install -g @serverless-devs/s
   ```

2. Configure your Aliyun RAM credentials. Use the `claude-mcp-user` AccessKey/SecretKey from `aliyun-handoff-secrets.md`:

   ```bash
   s config add
   # Provider: alibabacloud
   # AccessKeyID: <paste>
   # AccessKeySecret: <paste>
   # Alias: default
   ```

3. Resolve the **latest free Zhipu chat model**. Free models change over time. Verify the current model ID:

   ```bash
   curl -s -H "Authorization: Bearer $ZHIPU_API_KEY" \
     https://open.bigmodel.cn/api/paas/v4/models | jq -r '.data[].id' | grep -i flash
   ```

   If the API doesn't return a public list, check https://open.bigmodel.cn/dev/howuse/model and pick the latest documented free `*-flash` model. Common values: `glm-4.7-flash`, `glm-5-flash`. Use this string as `ZHIPU_MODEL_ID` below.

## Deploy

```bash
export ZHIPU_API_KEY="<your Zhipu key>"
export ZHIPU_MODEL_ID="glm-4.7-flash"   # or whatever step 3 resolved to
s deploy --use-local --assume-yes
```

`s deploy` prints a URL like `https://abc123.cn-beijing.fcapp.run/`. Save it:

```bash
echo "https://abc123.cn-beijing.fcapp.run" > function-compute/DEPLOYED_URL.txt
```

This file is gitignored. Pass the URL to `make_interactive.py` via `--endpoint`.

## Smoke test the deployed endpoint

```bash
URL=$(cat function-compute/DEPLOYED_URL.txt)

# Health
curl "$URL/health"
# {"ok":true}

# Valid 50-word draft
curl -X POST "$URL" -H "Content-Type: application/json" \
  -d '{"draft":"I went to the park yesterday with my friends. We played football for two hours. The weather was nice and sunny. After the game we got some ice cream. It was a great day and we plan to go again next weekend."}'
# {"corrected":"..."}

# Too-short rejection
curl -X POST "$URL" -H "Content-Type: application/json" \
  -d '{"draft":"too short"}'
# {"error":"请至少写 50 个词 / Please write at least 50 words. (Currently 2)"}

# OPTIONS preflight
curl -X OPTIONS "$URL" -i
# 204 No Content with CORS headers
```

## Updating

After editing `index.js`:

```bash
cd function-compute
ZHIPU_API_KEY=test-key node --test test/   # tests pass
s deploy --use-local --assume-yes
```

## Rotating the Zhipu key

Re-export the env var and redeploy:

```bash
export ZHIPU_API_KEY="<new key>"
cd function-compute
s deploy --use-local --assume-yes
```

(`s.yaml` references `${env('ZHIPU_API_KEY')}`, so `s deploy` picks up the new value from the shell environment and pushes it as the function's environment variable.)
