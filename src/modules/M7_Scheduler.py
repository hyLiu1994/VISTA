import os,threading,time
from typing import List, Dict, Any,Tuple, Callable
import json
import numpy as np
import logging
import concurrent.futures
from utils.utils import get_root_path
root_path=get_root_path()
from modules.M8_AnomalyDetection import handle_task_exception_with_retry
from modules.M9_Deredundancy import deredundancy

class KnowledgeUnitManager:
    def __init__(self, args):
        self.base_dir = os.path.join(root_path, 'results', args.exp_name,'KU')
        self.filename_prefix = f"knowledge_units_trajectory{args.trajectory_num}_len{args.trajectory_len}_seed{args.seed}"
        self.knowledge_unit_list = []
      
    def load_knowledge_unit_list(self, start_point: int):
        """Load existing knowledge units Returns: List of knowledge units processed"""
        if start_point == 0:
            return

        file_path = os.path.join(self.base_dir, f"{self.filename_prefix}_{start_point}.json")
        
        if os.path.exists(file_path):
            self.knowledge_unit_list = json.load(open(file_path, 'r', encoding='utf-8'))
            logging.info(f"file_path:{file_path}")
        return

    def save_knowledge_unit_list(self, end_point: int):
        """Save knowledge units Returns: Saved file path"""
        output_path = os.path.join(self.base_dir, f"{self.filename_prefix}_{end_point}.json")
        
        os.makedirs(self.base_dir, exist_ok=True)
        
        def default_converter(o):
            if isinstance(o, (np.integer, np.floating, np.ndarray, np.bool_)):
                return o.item() if hasattr(o, 'item') else o.tolist()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_unit_list, f, indent=2, ensure_ascii=False, default=default_converter)

    def infer_vs_vb(self, minimal_seg):
        mmsi = minimal_seg['mmsi'].iloc[0]
        sequence_id = minimal_seg['sequence_id'].iloc[0]
        current_segment_id = minimal_seg['segment_id'].iloc[0]
        
        vb = [] 
        vs = [] 
        
        # First try immediate neighbors
        for unit in self.knowledge_unit_list:
            unit_mmsi = unit.get('v_s', {}).get('MMSI')
            unit_seq = unit.get('v_s', {}).get('seq')
            unit_block = unit.get('v_s', {}).get('block')  

            if unit_mmsi is None or unit_seq is None or unit_block is None:
                continue
                
            if int(unit_mmsi) == int(mmsi) and int(unit_seq) == int(sequence_id):
                unit_segment_id = int(unit_block)

                if unit_segment_id == current_segment_id - 1 or unit_segment_id == current_segment_id + 1:
                    vb.append(unit.get('v_b'))
                    vs.append(unit.get('v_s'))
        
        if vb:
            return vb, vs
        
        # If no immediate neighbors, find all available segments for this sequence
        all_segments = []
        for unit in self.knowledge_unit_list:
            unit_mmsi = unit.get('v_s', {}).get('MMSI')
            unit_seq = unit.get('v_s', {}).get('seq')
            unit_block = unit.get('v_s', {}).get('block')  

            if unit_mmsi is None or unit_seq is None or unit_block is None:
                continue
                
            if int(unit_mmsi) == int(mmsi) and int(unit_seq) == int(sequence_id):
                unit_segment_id = int(unit_block)
                all_segments.append((unit_segment_id, unit.get('v_b'), unit.get('v_s')))
        
        # If no segments found at all, return empty
        if not all_segments:
            return vb, vs
        
        # Sort segments by segment_id to find closest ones
        all_segments.sort(key=lambda x: x[0])       

        closest_segments = []
        for seg_id, v_b, v_s in all_segments:
            distance = abs(seg_id - current_segment_id)
            closest_segments.append((distance, seg_id, v_b, v_s))

        closest_segments.sort(key=lambda x: x[0])
        for distance, seg_id, v_b, v_s in closest_segments[:2]: 
            vb.append(v_b)
            vs.append(v_s)
        
        return vb, vs

class ImputationResultsManager:
    def __init__(self, args):
        self.base_dir = os.path.join(root_path, 'results', args.exp_name, 'ImputationResults')
        self.filename_prefix = f"imputation_results_trajectory{args.trajectory_num}_len{args.trajectory_len}_seed{args.seed}"
        self.results_list = []
      
    def load_results_list(self, start_point: int, args):
        """Load existing imputation results Returns: List of results processed"""
        if start_point == 0:
            return
        end_point = args.end_point if args.pre_load else args.check_point
        file_path = os.path.join(self.base_dir, f"{self.filename_prefix}_{end_point}_{start_point}.json")
        if os.path.exists(file_path):
            self.results_list = json.load(open(file_path, 'r', encoding='utf-8'))
            logging.info(f"successful load file_path:{file_path}")
        return

    def save_results_list(self, end_point: int,args):
        """Save imputation results Returns: Saved file path"""
        output_path = os.path.join(self.base_dir, f"{self.filename_prefix}_{args.end_point}_{end_point}.json")
        
        os.makedirs(self.base_dir, exist_ok=True)
        
        def default_converter(o):
            if isinstance(o, (np.integer, np.floating, np.ndarray, np.bool_)):
                return o.item() if hasattr(o, 'item') else o.tolist()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results_list, f, indent=2, ensure_ascii=False, default=default_converter)
        
        logging.info(f"Saved imputation results to {output_path}")
        return output_path    
    
def build_segment_tasks(traj_df, sequences_to_process, mark_missing, start_idx, mode='SDKG'):
    tasks = []
    all_segments = traj_df[traj_df['sequence_id'].isin(sequences_to_process)][['sequence_id', 'segment_id']].drop_duplicates()
    seq_to_local = {sid: i for i, sid in enumerate(sequences_to_process)} 
    
    for _, row in all_segments.iterrows():
        actual_seq_id = row['sequence_id']
        segment_id = row['segment_id']
        seq_idx = seq_to_local[actual_seq_id]   
        
        if mode == 'SDKG':
            if mark_missing[seq_idx, segment_id] == 1:
                tasks.append({
                    'type': 'empty',
                    'seq_idx': seq_idx,
                    'actual_seq_id': actual_seq_id,
                    'segment_id': segment_id
                })
            else:
                segment_data = traj_df[
                    (traj_df['sequence_id'] == actual_seq_id) & 
                    (traj_df['segment_id'] == segment_id)
                ]
                tasks.append({
                    'type': 'process', 
                    'seq_idx': seq_idx,
                    'actual_seq_id': actual_seq_id,
                    'segment_id': segment_id,
                    'minimal_seg': segment_data.copy()
                })
                
        elif mode == 'imputation':
            if mark_missing[seq_idx, segment_id] == 1:
                sequence_data = traj_df[traj_df['sequence_id'] == actual_seq_id]
                minimal_seg = sequence_data[sequence_data['segment_id'].isin([segment_id-1, segment_id, segment_id+1])]
                minimal_seg.loc[minimal_seg['segment_id'] == segment_id, ['latitude', 'longitude']] = None
                tasks.append({
                    'seq_idx': seq_idx,
                    'actual_seq_id': actual_seq_id,
                    'segment_id': segment_id,
                    'minimal_seg': minimal_seg.copy(),
                    'sequence_data': sequence_data.copy()
                })
            else:
                tasks.append({
                    'type': 'skip',
                    'seq_idx': seq_idx,
                    'actual_seq_id': actual_seq_id, 
                    'segment_id': segment_id
                })
    
    logging.info(f"Built {len(tasks)} segments for {mode} processing")
    return tasks

def stack_schedule_sdk_construction(
    *,
    args,
    SDKG,
    ku_manager,
    tasks: List[Dict[str, Any]],
    process_single_segment_fn: Callable[[Any, Any, Dict[str, Any]], Dict[str, Any]],
    start_idx: int,
    end_idx: int,
    minimal_seg_nums: int,
) -> Tuple[Any, Any]:
    logging.info("Stack-Based Scheduler start (pseudo-structured pipeline)")

    sdk_write_lock = threading.Lock()
    last_checkpoint_traj = start_idx

    extraction_batch_size = args.max_concurrent
    deredundancy_batch_size = args.max_concurrent

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent)
    deredun_executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent)

    s_c_stack = tasks.copy()
    s_d_stack: List[Tuple[Dict[str, Any], Any, Any]] = []
    future_to_task: Dict[concurrent.futures.Future, Dict[str, Any]] = {}
    sd_inflight: List[concurrent.futures.Future] = []

    try:
        while s_c_stack or s_d_stack or sd_inflight:
            # Popbatch
            if s_c_stack:
                batch: List[Dict[str, Any]] = []
                for _ in range(min(extraction_batch_size, len(s_c_stack))):
                    batch.append(s_c_stack.pop())

                #Parallel
                batch_futures = []
                for t in batch:
                    f = executor.submit(process_single_segment_fn, SDKG, args, t)
                    future_to_task[f] = t
                    batch_futures.append(f)
                    logging.info(f"[S_c submit] seq {t['seq_idx']} seg {t['segment_id']}")

                concurrent.futures.wait(batch_futures, return_when=concurrent.futures.ALL_COMPLETED)

                for f in batch_futures:
                    #Anomaly detection
                    t = future_to_task.pop(f)
                    result, should_retry = handle_task_exception_with_retry(
                        f, t, ku_manager.knowledge_unit_list, "SDKG", args.max_retries, SDKG
                    )
                    #success
                    if result is not None and result.get('result'):
                        #push to Sd
                        s_d_stack.append((result['result'], result.get('new_flags'), result.get('is_new_vf')))
                        logging.info(f"[S_c→S_d push] seq {t['seq_idx']} seg {t['segment_id']}")
                    #retry times < max retry times
                    elif should_retry:
                        t['retry_count'] = t.get('retry_count', 0) + 1
                        s_c_stack.append(t)
                        logging.warning(f"[Retry queued] seq {t['seq_idx']} seg {t['segment_id']} (#{t['retry_count']})")
                    #fail
                    else:
                        logging.error(f"[Extract failed] seq {t['seq_idx']} seg {t['segment_id']} after {args.max_retries}")

            if s_d_stack and (len(sd_inflight) < deredundancy_batch_size):
                #Popbatch
                batch_kus, batch_flags, batch_vf = [], [], []
                for _ in range(min(extraction_batch_size, len(s_d_stack))):
                    ku, flg, vf = s_d_stack.pop()
                    batch_kus.append(ku); batch_flags.append(flg); batch_vf.append(vf)
                fb = deredun_executor.submit(deredundancy, args, SDKG,list(batch_kus), list(batch_flags), list(batch_vf))
                sd_inflight.append(fb)
                
            #Update the SDKG
            if sd_inflight:
                done, _ = concurrent.futures.wait(sd_inflight, timeout=0, return_when=concurrent.futures.FIRST_COMPLETED)
                for fb in list(done):
                    try:
                        rlist = fb.result()
                    except Exception as e:
                        logging.exception(f"error: {e}")
                        rlist = None

                    if rlist:
                        results = rlist if isinstance(rlist, list) else [rlist]
                        if results:
                            try:
                                with sdk_write_lock:
                                    SDKG.update_SDK_graph_per_batch(results)
                            except Exception as e:
                                logging.exception(f"[SDKG.update per batch failed] {e}")

                    sd_inflight.remove(fb)

            # checkpoint
            current_traj_idx = len(ku_manager.knowledge_unit_list) // minimal_seg_nums
            target_traj = min(last_checkpoint_traj + args.process_length, end_idx)
            if current_traj_idx > last_checkpoint_traj and current_traj_idx >= target_traj:
                ku_manager.save_knowledge_unit_list(current_traj_idx)
                with sdk_write_lock:
                    SDKG.save_SDKG(str(current_traj_idx))
                logging.info(f"[Checkpoint] traj={current_traj_idx}")
                last_checkpoint_traj = current_traj_idx

            time.sleep(0.001)

        # Final checkpoint
        final_traj_idx = len(ku_manager.knowledge_unit_list) // minimal_seg_nums
        if final_traj_idx > last_checkpoint_traj:
            ku_manager.save_knowledge_unit_list(final_traj_idx)
            with sdk_write_lock:
                SDKG.save_SDKG(str(final_traj_idx))
            logging.info(f"[Final checkpoint] traj={final_traj_idx}")

    finally:
        executor.shutdown(wait=True)
        deredun_executor.shutdown(wait=True)

    logging.info("Stack-Based Scheduler finished")
    return SDKG, ku_manager

def stack_schedule_imputation(
    *,
    args,
    SDKG,
    result_manager,
    tasks: List[Dict[str, Any]],
    process_single_segment_fn: Callable[[Dict[str, Any], Any, Any, Any], Dict[str, Any]],
    context_info_manager: Any,
    start_idx: int,
    end_idx: int,
    minimal_seg_nums: int,
) -> Any:
    logging.info("Stack-Based Scheduler (Trajectory Imputation) start")

    s_i_stack = tasks.copy()
    last_checkpoint_traj = start_idx
    batch_size = args.max_concurrent

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent)

    try:
        while s_i_stack:
            #POPBATCH
            batch = []
            for _ in range(min(batch_size, len(s_i_stack))):
                batch.append(s_i_stack.pop())

            batch_futures = []
            future_to_task: Dict[concurrent.futures.Future, Dict[str, Any]] = {}
            for task in batch:
 
                fut = executor.submit(process_single_segment_fn, task, args, SDKG, context_info_manager)
                future_to_task[fut] = task
                batch_futures.append(fut)
                if task.get('type') != 'skip':
                    logging.info(f"[S_i submit] seq {task['seq_idx']} seg {task['segment_id']}")

            concurrent.futures.wait(batch_futures, return_when=concurrent.futures.ALL_COMPLETED)

            for fut in batch_futures:
                #Anomaly detect
                task = future_to_task[fut]
                result, should_retry = handle_task_exception_with_retry(
                    fut, task, result_manager.results_list, "imputation", args.max_retries, SDKG
                )
                #success
                if result is not None:
                    if task.get('type') != 'skip':
                        logging.info(f"[Imputed] seq {task['seq_idx']} seg {task['segment_id']}")
                    else:
                        logging.info(f"[Skipped] seq {task['seq_idx']} seg {task['segment_id']}")
                #retry times < max retry times
                elif should_retry:
                    task['retry_count'] = task.get('retry_count', 0) + 1
                    s_i_stack.append(task)
                    logging.warning(f"[Retry queued] seq {task['seq_idx']} seg {task['segment_id']} (#{task['retry_count']})")
                #fail
                else:
                    logging.error(f"[Failed] seq {task['seq_idx']} seg {task['segment_id']} after {args.max_retries}")
            
            #check point
            current_traj_idx = len(result_manager.results_list) // minimal_seg_nums
            target_traj = min(last_checkpoint_traj + args.process_length, end_idx)
            if current_traj_idx > last_checkpoint_traj and current_traj_idx >= target_traj:
                result_manager.save_results_list(current_traj_idx, args)
                logging.info(f"[Checkpoint] traj={current_traj_idx}")
                last_checkpoint_traj = current_traj_idx

            time.sleep(0.01)

        #Final Checkpoint
        final_traj_idx = len(result_manager.results_list) // minimal_seg_nums
        if final_traj_idx > last_checkpoint_traj:
            result_manager.save_results_list(final_traj_idx, args)

    finally:
        executor.shutdown(wait=True)

    return result_manager

