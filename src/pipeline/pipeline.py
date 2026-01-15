import logging
from typing import List, Dict, Any
from src.utils.utils import get_root_path
from src.modules.M7_Scheduler import build_segment_tasks,stack_schedule_sdk_construction, stack_schedule_imputation
root_path = get_root_path()

from src.modules.M1_StaticSpatialEncoder import generate_vs
from src.modules.M2_BehaviorAbstraction import generate_vb
from src.modules.M3_MethodBuilder import generate_vf
from src.modules.M4_BehaviorEstimator import behavior_estimator
from src.modules.M5_MethodSelector import method_selector
from src.modules.M6_ExplanationComposer import explanation_composer

def SDKG_process_single_segment(SDKG,args,task):
        if task['type'] == 'empty':
            logging.info(f"Sequence {task['seq_idx']} segment {task['segment_id']} is masked, adding empty unit")
            return {'task': task, 'result': {}}
        
        logging.info(f"Processing sequence {task['seq_idx']} segment {task['segment_id']}")
        minimal_seg = task['minimal_seg']
        v_s = generate_vs(minimal_seg, minimal_seg['mmsi'].iloc[0], task['actual_seq_id'], task['segment_id'])
        v_b, new_flags = generate_vb(args, minimal_seg, SDKG)                        
        v_f, is_new_vf = generate_vf(args, v_b, SDKG, minimal_seg) if v_b else None
        
        return {'task': task, 'result': {"v_s": v_s, "v_b": v_b, "v_f": v_f}, 'new_flags':new_flags, 'is_new_vf':is_new_vf}

def process_single_segment(task,args,SDKG,context_info_manager):
    if task.get('type') == 'skip':
        logging.info(f"Sequence {task['seq_idx']} segment {task['segment_id']} isn't masked, skipping")
        return {'task': task, 'result': {}}

    logging.info(f"Processing sequence {task['seq_idx']} segment {task['segment_id']}")
    minimal_seg = task['minimal_seg']
    Cb, vb_f = behavior_estimator(args, minimal_seg, SDKG, context_info_manager)
    Cf, vf_f = method_selector(args, ([vb_f['selected_movement_id']],[SDKG.find_vb_attribute(vb_f['selected_movement_id'])]), minimal_seg, SDKG) if Cb else (None, None)
    Ep = explanation_composer(args, minimal_seg, Cb, Cf, vb_f, vf_f, SDKG, context_info_manager) if Cb else None
    
    result = {"sequence_id": task['actual_seq_id'],"segment_id": task['segment_id'],"mmsi": minimal_seg['mmsi'].iloc[0],"behavior_estimator": vb_f,"method_selector": vf_f,"explanation_composer": Ep}
    
    return {'task': task, 'result': result}

def SDKG_Construction_Multithreading(
    args,
    trajectory_data,
    ku_manager,
    SDKG,
) -> List[Dict[str, Any]]:
    logging.info("\n========= SDKG Construction =========")
    traj_df, mark_missing = trajectory_data
    start_idx, end_idx = args.check_point, args.end_point
    sequences_to_process = traj_df['sequence_id'].unique()[start_idx:end_idx]

    SDKG.load_SDKG(start_idx)
    ku_manager.load_knowledge_unit_list(start_idx)

    minimal_seg_nums = args.trajectory_len // args.mini_segment_len
    mark_window = mark_missing[start_idx:end_idx, :]

    tasks = build_segment_tasks(traj_df, sequences_to_process, mark_window, start_idx, mode='SDKG')
    logging.info(f"Collected {len(tasks)} segments for processing")

    SDKG, ku_manager = stack_schedule_sdk_construction(
        args=args,
        SDKG=SDKG,
        ku_manager=ku_manager,
        tasks=tasks,
        process_single_segment_fn=SDKG_process_single_segment,
        start_idx=start_idx,
        end_idx=end_idx,
        minimal_seg_nums=minimal_seg_nums,
    )

    return SDKG, ku_manager



def Trajectory_Imputation_Multithreading(
    args,
    trajectory_data,
    context_info_manager,
    SDKG,
    result_manager
) -> List[Dict[str, Any]]:
    logging.info("\n========= Trajectory Imputation =========")
    traj_df, mark_missing = trajectory_data
    start_idx, end_idx = args.check_point, args.end_point
    sequences_to_process = traj_df['sequence_id'].unique()[start_idx:end_idx]

    result_manager.load_results_list(start_idx, args)

    minimal_seg_nums = args.trajectory_len // args.mini_segment_len
    mark_window = mark_missing[start_idx:end_idx, :]

    tasks = build_segment_tasks(traj_df, sequences_to_process, mark_window, start_idx, mode='imputation')
    logging.info(f"Collected {len(tasks)} segments for processing "
                 f"({len([t for t in tasks if t.get('type') != 'skip'])} need imputation)")

    result_manager = stack_schedule_imputation(
        args=args,
        SDKG=SDKG,
        result_manager=result_manager,
        tasks=tasks,
        process_single_segment_fn=process_single_segment,
        context_info_manager=context_info_manager,
        start_idx=start_idx,
        end_idx=end_idx,
        minimal_seg_nums=minimal_seg_nums,
    )

    return result_manager