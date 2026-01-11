import logging
import concurrent
def handle_task_exception_with_retry(future, task, result_list, task_type="task", max_retries=3, SDKG=None):
    if 'retry_count' not in task:
        task['retry_count'] = 0
    
    try:
        result = future.result(timeout=120)
        if 'error' in result:
            task['retry_count'] += 1
            if task['retry_count'] <= max_retries:
                logging.warning(f"Failed {task_type} sequence {task['seq_idx']} segment {task['segment_id']} (attempt {task['retry_count']}/{max_retries}): {result['error']}")
                return None, True 
            else:
                logging.error(f"Failed {task_type} sequence {task['seq_idx']} segment {task['segment_id']} after {max_retries} attempts: {result['error']}")
                if task_type == "SDKG":
                    empty_result = {"v_s": {}, "v_b": None, "v_f": None}
                else: 
                    empty_result = {
                        "sequence_id": task['actual_seq_id'],
                        "segment_id": task['segment_id'],
                        "mmsi": task['minimal_seg']['mmsi'].iloc[0] if 'minimal_seg' in task else "unknown",
                        "behavior_estimator": None,
                        "method_selector": None,
                        "explanation_composer": None
                    }
                result_list.append(empty_result)
                return None, False  
        else:
            if task_type == "imputation" and result.get('result') and result['result'].get('method_selector'):
                vf_id = result['result']['method_selector'].get('selected_function_id')
                if vf_id and SDKG and not SDKG.check_vf_exists(vf_id):
                    task['retry_count'] += 1
                    if task['retry_count'] <= max_retries:
                        logging.warning(f"VF ID {vf_id} not found in SDKG for sequence {task['seq_idx']} segment {task['segment_id']} (attempt {task['retry_count']}/{max_retries}), retrying...")
                        return None, True
                    else:
                        logging.error(f"VF ID {vf_id} not found in SDKG for sequence {task['seq_idx']} segment {task['segment_id']} after {max_retries} attempts")
                        empty_result = {
                            "sequence_id": task['actual_seq_id'],
                            "segment_id": task['segment_id'],
                            "mmsi": task['minimal_seg']['mmsi'].iloc[0] if 'minimal_seg' in task else "unknown",
                            "behavior_estimator": None,
                            "method_selector": None,
                            "explanation_composer": None
                        }
                        result_list.append(empty_result)
                        return None, False
            
            task['retry_count'] = 0
            if task_type == "SDKG":
                result_list.append(result['result'])
            else: 
                result_list.append(result['result'])
            return result, False
            
    except concurrent.futures.TimeoutError:
        task['retry_count'] += 1
        if task['retry_count'] <= max_retries:
            logging.warning(f"Timeout processing {task_type} sequence {task['seq_idx']} segment {task['segment_id']} (attempt {task['retry_count']}/{max_retries})")            
            return None, True
        else:
            logging.error(f"Timeout processing {task_type} sequence {task['seq_idx']} segment {task['segment_id']} after {max_retries} attempts")
            if task_type == "SDKG":
                empty_result = {"v_s": {}, "v_b": None, "v_f": None}
            else:
                empty_result = {
                    "sequence_id": task['actual_seq_id'],
                    "segment_id": task['segment_id'],
                    "mmsi": task['minimal_seg']['mmsi'].iloc[0] if 'minimal_seg' in task else "unknown",
                    "behavior_estimator": None,
                    "method_selector": None,
                    "explanation_composer": None
                }
            result_list.append(empty_result)
            return None, False
            
    except Exception as e:
        task['retry_count'] += 1
        if task['retry_count'] <= max_retries:
            logging.warning(f"result:{future.result}")
            logging.warning(f"Unexpected error processing {task_type} sequence {task['seq_idx']} segment {task['segment_id']} (attempt {task['retry_count']}/{max_retries}): {e}")
            return None, True
        else:
            logging.error(f"Unexpected error processing {task_type} sequence {task['seq_idx']} segment {task['segment_id']} after {max_retries} attempts: {e}")
            if task_type == "SDKG":
                empty_result = {"v_s": {}, "v_b": None, "v_f": None}
            else:
                empty_result = {
                    "sequence_id": task['actual_seq_id'],
                    "segment_id": task['segment_id'],
                    "mmsi": task['minimal_seg']['mmsi'].iloc[0] if 'minimal_seg' in task else "unknown",
                    "behavior_estimator": None,
                    "method_selector": None,
                    "explanation_composer": None
                }
            result_list.append(empty_result)
            return None, False