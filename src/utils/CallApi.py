import openai
import time
import logging
from ..modules.Prompt import USAGE_STAT
total_prompt_tokens = 0
total_completion_tokens = 0

def _accumulate_usage(purpose, usage, elapsed_sec):
    global total_prompt_tokens, total_completion_tokens
    if not usage:
        return
    pr = getattr(usage, "prompt_tokens", 0) or 0
    cp = getattr(usage, "completion_tokens", 0) or 0
    tt = getattr(usage, "total_tokens", 0) or (pr + cp)
    total_prompt_tokens += pr
    total_completion_tokens += cp
    
    g = USAGE_STAT[purpose]
    g["prompt"]     += pr
    g["completion"] += cp
    g["total"]      += tt
    g["time_sec"]   += float(elapsed_sec)
    g["calls"]      += 1


def call_qwen_api(args,prompt,llm_model,llm_purpose):
    client = openai.OpenAI(
        api_key=args.llm_api_key,
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
    )
    t0 = time.time()
    completion = client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": "You are a maritime data analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        extra_body={"enable_thinking": False}
    )
    elapsed = time.time() - t0

    # usage statistics
    usage = getattr(completion, "usage", None)
    _accumulate_usage(llm_purpose, usage, elapsed)

    # The console displays staged statistics
    if usage:
        logging.info(f"[{llm_purpose.upper()}] +{usage.total_tokens} tok "
              f"(in {getattr(usage,'prompt_tokens',0)}/out {getattr(usage,'completion_tokens',0)}), "
              f"time {elapsed:.2f}s")
    else:
        logging.info(f"[{llm_purpose.upper()}] No usage field, time {elapsed:.2f}s")
        
    logging.info(f"Current Stats - Total: {total_prompt_tokens + total_completion_tokens} tokens "
        f"(Input: {total_prompt_tokens}, Output: {total_completion_tokens})")

    for purpose, stats in USAGE_STAT.items():
        if stats["calls"] > 0:
            avg_time = stats["time_sec"] / stats["calls"] if stats["calls"] > 0 else 0
            logging.info(f"  {purpose:12}: {stats['calls']:2d} calls, "
                f"{stats['total']:5d} tokens "
                f"(in:{stats['prompt']:4d}/out:{stats['completion']:4d}), "
                f"time:{stats['time_sec']:6.2f}s (avg:{avg_time:.2f}s)")

    return completion.choices[0].message.content