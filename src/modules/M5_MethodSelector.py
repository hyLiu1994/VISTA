from src.utils.CallApi import call_qwen_api
from modules.Prompt import Method_Selector_Prompt
import re
from typing import Dict
import logging
def extract_selection_methods(llm_output: str) -> Dict[str, str]:
    match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", llm_output, re.DOTALL)
    text = match.group(1) if match else llm_output

    func_id = re.search(r"Selected\s*Function\s*ID\s*:\s*(.+)", text, re.I)
    stat_support = re.search(r"Statistical\s*Support\s*:\s*(.+?)(?=\n\s*Reasoning)", text, re.I | re.S)
    reasoning = re.search(r"Reasoning\s*:\s*(.+?)(?=\n\s*Imputation)", text, re.I | re.S)
    action = re.search(r"Imputation\s*Action\s*:\s*(.+)", text, re.I | re.S)
    
    result = {
        'selected_function_id': func_id.group(1).strip() if func_id else "",
        'statistical_support': stat_support.group(1).strip() if stat_support else "",
        'reasoning': reasoning.group(1).strip() if reasoning else "",
        'imputation_action': action.group(1).strip() if action else ""
    }
    
    return result if any(result.values()) else {}

def method_selector(args,Cb,minimal_seg,SDKG):
    logging.info("START M5")
    Cf=SDKG.select_Cf_Cb(args,Cb)
    #logging.info(f"Selected candidate functions: {Cf}")
    dot_graph=SDKG.generate_induce_graph(None,Cb,Cf)
    #logging.info(f"Generated dot graph for method selection:\n{dot_graph}")
    def build_prompt():
        return Method_Selector_Prompt.format(
            dot_text=dot_graph,
            functions_text=Cf,
            movement_text=Cb,
            rows_text=minimal_seg
        )
    
    raw_output = call_qwen_api(args, build_prompt(),args.analysis_llm,'selection')
    #logging.info(f"Raw LLM output for method selection:\n{raw_output}")
    vf = extract_selection_methods(raw_output)
    #logging.info(f"Extracted method selection results: {vf}")
    return Cf,vf