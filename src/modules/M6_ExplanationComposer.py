import re
from typing import Dict
from src.utils.CallApi import call_qwen_api
from src.modules.Prompt import Explanation_Composer_Prompt
import logging
def extract_explanation(llm_output: str) -> Dict[str, str]:
    match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", llm_output, re.DOTALL)
    text = match.group(1) if match else llm_output

    rule_cue = re.search(r"Regulatory\s*Rule\s*Cue\s*:\s*(.+)", text, re.I | re.S)
    op_protocol = re.search(r"Operational\s*Protocol\s*Rationale\s*:\s*(.+)", text, re.I | re.S)
    
    result = {
        'regulatory_rule_cue': rule_cue.group(1).strip() if rule_cue else "",
        'operational_protocol_rationale': op_protocol.group(1).strip() if op_protocol else ""
    }
    
    return result if any(result.values()) else {}

def explanation_composer(args,minimal_seg,Cb,Cf,vb_f,vf_f,SDKG,context_information):
    logging.info("START M6")
    vb_c,vs_c=context_information.infer_vs_vb(minimal_seg)

    dot_graph=SDKG.generate_induce_graph(vs_c,Cb,Cf)
    #logging.info(f"Generated dot graph for explanation composition:\n{dot_graph}")
    
    def build_prompt():
        return Explanation_Composer_Prompt.format(
            dot_text=dot_graph,
            movement_desc=vb_f,
            function_desc=vf_f,
            vessels_desc_block=vs_c,
            vessels_behavior_pattern=vb_c
        )
    
    raw_output = call_qwen_api(args, build_prompt(),args.analysis_llm,'explanation')
    #logging.info(f"Raw LLM output for explanation composition:\n{raw_output}")
    explanations = extract_explanation(raw_output)
    #logging.info(f"Extracted explanations: {explanations}")
    return explanations