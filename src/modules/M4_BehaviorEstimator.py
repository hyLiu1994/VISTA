from src.utils.CallApi import call_qwen_api
from src.modules.Prompt import Behavior_Estimator_Prompt
import re
from typing import Dict
import logging

def extract_behavior_selection(llm_output: str) -> Dict[str, str]:
    match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", llm_output, re.DOTALL)
    text = match.group(1) if match else llm_output

    movement_id = re.search(r"Selected\s*Movement\s*ID\s*:\s*(.+)", text, re.I)
    graph_support = re.search(r"Graph\s*Support\s*:\s*(.+?)(?=\n\s*Contextual)", text, re.I | re.S)
    contextual_just = re.search(r"Contextual\s*Justification\s*:\s*(.+)", text, re.I | re.S)
    
    result = {
        'selected_movement_id': movement_id.group(1).strip() if movement_id else "",
        'graph_support': graph_support.group(1).strip() if graph_support else "",
        'contextual_justification': contextual_just.group(1).strip() if contextual_just else ""
    }
    
    return result if any(result.values()) else {}

def behavior_estimator(args,minimal_seg,SDKG,context_information):
    logging.info("START M4")
    vb_c,vs_c=context_information.infer_vs_vb(minimal_seg)
    
    Cb=SDKG.select_Cb(args,vs_c)
    
    dot_graph=SDKG.generate_induce_graph(vs_c , Cb , None)
    #logging.info(f"Generated dot graph for behavior estimation:\n{dot_graph}")  
    
    def build_prompt():
        return Behavior_Estimator_Prompt.format(
            boundary_text=vb_c,
            dot_text=dot_graph,
            context_vessels=vs_c,
            movement_text=Cb,
            rows_text=minimal_seg,
            top_k=args.top_k
        )
    
    raw_output = call_qwen_api(args, build_prompt(),args.analysis_llm,'selection')
    #logging.info(f"Behavior Estimator LLM Output:\n{raw_output}")
    vb = extract_behavior_selection(raw_output)
    #logging.info(f"Extracted Behavior Selection: {vb}")
    
    return Cb,vb