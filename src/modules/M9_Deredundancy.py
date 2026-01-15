from src.utils.CallApi import call_qwen_api
from src.modules.Prompt import Redundancy_Analysis_Prompt
import logging

def deredundancy(args, SDKG, knowledge_unit_list, new_flags_list,vf_flags_list):
    
    if not knowledge_unit_list:
        return knowledge_unit_list

    vb_data_text, all_vb_data, dict_mapping = prepare_vb_data(SDKG, knowledge_unit_list, new_flags_list)
    logging.info(f"vb_data_text:{vb_data_text}")
    logging.info(f"all_vb_data:{all_vb_data}")
    logging.info(f"dict_mapping:{dict_mapping}")
    
    vf_data_text = prepare_vf_data(SDKG, knowledge_unit_list, vf_flags_list)
    logging.info(f"vf_data_text:{vf_data_text}")
    
    if vb_data_text or vf_data_text:
        combined_redundancy_analysis(args, SDKG, vb_data_text, vf_data_text, all_vb_data, dict_mapping,knowledge_unit_list)

    return knowledge_unit_list

def prepare_vb_data(SDKG, knowledge_unit_list, new_flags_list):

    attribute_dicts = SDKG.get_vb_attributes_dicts()
    dict_mapping = {
        "speed_profile": attribute_dicts["speed_dict"],
        "course_change": attribute_dicts["course_dict"],
        "heading_fluctuation": attribute_dicts["heading_dict"], 
        "intent": attribute_dicts["intent_dict"]
    }

    all_vb_data = []
    vb_data_text = ""
    
    for i, (knowledge_unit, new_flags) in enumerate(zip(knowledge_unit_list, new_flags_list)):
        if not knowledge_unit or 'v_b' not in knowledge_unit:
            continue
            
        vb_data = {
            'index': i,
            'knowledge_unit': knowledge_unit,
            'attributes_to_check': {},
            'new_flags': new_flags
        }

        for attribute, is_new in new_flags.items():
            if is_new and attribute in dict_mapping and attribute in knowledge_unit['v_b']:
                current_value = knowledge_unit['v_b'][attribute]
                dict_values = list(dict_mapping[attribute].keys())
                vb_data['attributes_to_check'][attribute] = {
                    'current_value': current_value,
                    'dict_values': dict_values
                }
        
        if vb_data['attributes_to_check']:
            all_vb_data.append(vb_data)

            sequence_id = knowledge_unit.get('sequence_id', 'unknown')
            segment_id = knowledge_unit.get('segment_id', 'unknown')
            vb_data_text += f"\nVB {i} (Sequence {sequence_id}, Segment {segment_id}):\n"
            
            for attribute, data in vb_data['attributes_to_check'].items():
                current_value = data['current_value']
                dict_values = data['dict_values']
                
                vb_data_text += f"  Attribute: {attribute}\n"
                vb_data_text += f"  Current value: {current_value}\n"
                vb_data_text += f"  Dictionary values ({len(dict_values)}):\n"
                for value in dict_values:
                    vb_data_text += f"    - {value}\n"
                vb_data_text += "\n"
    
    return vb_data_text, all_vb_data, dict_mapping

def prepare_vf_data(SDKG, knowledge_unit_list, vf_flags_list):
    """Prepare VF data for redundancy analysis, only process when vf_flag is True"""
    all_vfs = {}

    for i, (knowledge_unit, is_new_vf) in enumerate(zip(knowledge_unit_list, vf_flags_list)):
        if is_new_vf and knowledge_unit and 'v_f' in knowledge_unit and knowledge_unit['v_f']:
            code = knowledge_unit['v_f'].get('spatial_function', '')
            if code:
                vf_id = knowledge_unit['v_f'].get('vf_id', f"temp_vf_{i}")
                all_vfs[vf_id] = {
                    'code': code,
                    'knowledge_unit': knowledge_unit,
                    'source': 'current_batch'
                }

    existing_vf_nodes = SDKG.load_vf_node()
    for vf_id, vf_node in existing_vf_nodes.items():
        if 'code' in vf_node:
            all_vfs[vf_id] = {
                'code': vf_node['code'],
                'knowledge_unit': None,
                'source': 'SDKG'
            }
    
    if len(all_vfs) <= 1:
        return ""
        
    vf_data_text = "SPATIAL FUNCTIONS - Code Samples with IDs:\n"
    for vf_id, data in all_vfs.items():
        code = data['code']
        source = data['source']
        vf_data_text += f"\nFunction ID: {vf_id} (from {source}):\n```python\n{code}\n```\n"
    
    return vf_data_text

def combined_redundancy_analysis(args, SDKG, vb_data_text, vf_data_text, all_vb_data, dict_mapping,knowledge_unit_list):

    prompt = Redundancy_Analysis_Prompt.format(
        vb_data_text=vb_data_text if vb_data_text else "No behavior patterns to analyze",
        vf_data_text=vf_data_text if vf_data_text else "No spatial functions to analyze"
    )
    
    try:
        response = call_qwen_api(args, prompt, args.analysis_llm, 'selection')
        logging.info(f"Redundancy analysis response: {response}")

        if vb_data_text:
            parse_and_clean_vb_response(SDKG, all_vb_data, dict_mapping, response)

        if vf_data_text:
            parse_and_clean_vf_response(SDKG, knowledge_unit_list, response)
            
    except Exception as e:
        logging.error(f"Combined redundancy analysis failed: {e}")
        
def parse_and_clean_vb_response(SDKG, all_vb_data, dict_mapping, response):
    total_updated = 0
    
    if "BEHAVIOR_REDUNDANCY:" in response:
        behavior_section = response.split("BEHAVIOR_REDUNDANCY:")[1].split("KEEP_UNIQUE:")[0]

        attribute_redundancy = {}
        current_attribute = None
        
        for line in behavior_section.split('\n'):
            line = line.strip()
            
            if line.endswith(':'):
                current_attribute = line[:-1]
                attribute_redundancy[current_attribute] = {}
                
            elif line.startswith('-') and '|' in line and current_attribute:
                primary = line.split('|')[0].replace('-', '').strip()
                redundant_part = line.split('|')[1].strip().strip('[]')
                redundant_terms = [term.strip().strip('"\'') for term in redundant_part.split(',')]
                
                for redundant in redundant_terms:
                    if redundant and redundant != primary:
                        attribute_redundancy[current_attribute][redundant] = primary

        sdkg_cleaned_count = SDKG.clean_dicts(attribute_redundancy)

        for attribute, redundancy_mapping in attribute_redundancy.items():
            for vb_data in all_vb_data:
                knowledge_unit = vb_data['knowledge_unit']
                
                if attribute in knowledge_unit['v_b']:
                    current_full_value = knowledge_unit['v_b'][attribute]

                    for redundant_term, primary_term in redundancy_mapping.items():
                        if redundant_term in current_full_value:
                            knowledge_unit['v_b'][attribute] = primary_term
                            total_updated += 1
                            logging.info(f"VB {vb_data['index']} {attribute}: '{redundant_term}' -> '{primary_term}'")
                            break  
    
    logging.info(f"VB data: updated {total_updated} values | SDKG dict: cleaned {sdkg_cleaned_count} terms")
    
def parse_and_clean_vf_response(SDKG, knowledge_unit_list, response):
    cleaned_count = 0
    
    try:
        if "FUNCTION_REDUNDANCY:" in response:
            section = response.split("FUNCTION_REDUNDANCY:")[1].split("KEEP_UNIQUE:")[0]

            redundancy_mapping = {}
            for line in section.split('\n'):
                line = line.strip()
                if line.startswith('-') and '|' in line:
                    primary_id = line.split('|')[0].replace('-', '').strip()
                    redundant_part = line.split('|')[1].strip().strip('[]')
                    redundant_ids = [id_str.strip().strip('"\'') for id_str in redundant_part.split(',')]
                    
                    for redundant_id in redundant_ids:
                        if redundant_id and redundant_id != primary_id:
                            redundancy_mapping[redundant_id] = primary_id

            logging.info(f"Parsed redundancy mapping: {redundancy_mapping}")

            def resolve_final_target(node_id, visited=None):
                if visited is None:
                    visited = set()
                
                if node_id in visited:
                    return node_id
                
                visited.add(node_id)
                
                if node_id not in redundancy_mapping:
                    return node_id
                
                target = redundancy_mapping[node_id]
                if target == node_id:
                    return node_id
                
                return resolve_final_target(target, visited)

            final_targets = {}
            all_nodes = set(list(redundancy_mapping.keys()) + list(redundancy_mapping.values()))
            for node in all_nodes:
                final_targets[node] = resolve_final_target(node)
                
            # Case 1: Identify temp groups containing permanent nodes
            temp_groups_with_permanent = {}
            for primary_id in set(redundancy_mapping.values()):
                if primary_id.startswith('temp_vf_'):
                    permanent_nodes = []
                    temp_nodes = []
                    
                    for redundant_id, target_id in redundancy_mapping.items():
                        if target_id == primary_id:
                            if redundant_id.startswith('vf_') and not redundant_id.startswith('vf_temp'):
                                permanent_nodes.append(redundant_id)
                            elif redundant_id.startswith('temp_vf_'):
                                temp_nodes.append(redundant_id)
                    
                    if permanent_nodes:
                        temp_groups_with_permanent[primary_id] = {
                            'permanent_nodes': permanent_nodes,
                            'temp_nodes': temp_nodes
                        }

            processed_permanent = set()
            temp_to_permanent = {}

            #Merge permanent nodes within temp groups
            for temp_primary, group_data in temp_groups_with_permanent.items():
                permanent_nodes = group_data['permanent_nodes']
                temp_nodes = group_data['temp_nodes']
                
                if not permanent_nodes:
                    continue
                
                main_permanent = permanent_nodes[0]
                
                for permanent_node in permanent_nodes[1:]:
                    if permanent_node not in processed_permanent:
                        if SDKG.merge_vf_nodes(main_permanent, permanent_node):
                            logging.info(f"Merged permanent VF nodes: {permanent_node} -> {main_permanent}")
                        processed_permanent.add(permanent_node)
                
                processed_permanent.add(main_permanent)
                
                temp_to_permanent[temp_primary] = main_permanent
                for temp_node in temp_nodes:
                    temp_to_permanent[temp_node] = main_permanent
                    
            # Case 2: Handle direct permanent-to-permanent redundancy
            for redundant_id, primary_id in redundancy_mapping.items():
                if (redundant_id.startswith('vf_') and not redundant_id.startswith('vf_temp') and
                    primary_id.startswith('vf_') and not primary_id.startswith('vf_temp')):
                    if redundant_id not in processed_permanent and primary_id not in processed_permanent:
                        if SDKG.merge_vf_nodes(primary_id, redundant_id):
                            logging.info(f"Merged permanent VF nodes: {redundant_id} -> {primary_id}")
                            processed_permanent.add(redundant_id)
            
            # Case 3: Add direct temp-to-permanent mappings
            for redundant_id, primary_id in redundancy_mapping.items():
                if (redundant_id.startswith('temp_vf_') and 
                    primary_id.startswith('vf_') and not primary_id.startswith('vf_temp')):
                    if redundant_id not in temp_to_permanent:
                        temp_to_permanent[redundant_id] = primary_id
            
            #Replace temp VF content with permanent VF content
            for temp_id, permanent_id in temp_to_permanent.items():
                try:
                    temp_index = int(temp_id.split('_')[2])
                    if 0 <= temp_index < len(knowledge_unit_list):
                        temp_ku = knowledge_unit_list[temp_index]
                        vf_nodes = SDKG.load_vf_node()
                        
                        if permanent_id in vf_nodes:
                            temp_ku['v_f'] = {
                                'describe_of_function': vf_nodes[permanent_id].get('description', ''),
                                'spatial_function': vf_nodes[permanent_id].get('code', ''),
                                'vf_id': permanent_id
                            }
                            cleaned_count += 1
                            logging.info(f"Replaced temp VF {temp_id} with permanent VF {permanent_id}")
                except (ValueError, IndexError) as e:
                    logging.error(f"Error processing temp VF: {temp_id}, error: {e}")

            # Case 4: Handle  temp-to-temp redundancy
            remaining_temp_mapping = {}
            for redundant_id, primary_id in redundancy_mapping.items():
                if (redundant_id.startswith('temp_vf_') and 
                    redundant_id not in temp_to_permanent and
                    primary_id.startswith('temp_vf_') and
                    primary_id not in temp_to_permanent):
                    remaining_temp_mapping[redundant_id] = primary_id

            for redundant_id, primary_id in remaining_temp_mapping.items():
                try:
                    redundant_index = int(redundant_id.split('_')[2])
                    primary_index = int(primary_id.split('_')[2])
                    
                    if (0 <= redundant_index < len(knowledge_unit_list) and 
                        0 <= primary_index < len(knowledge_unit_list)):
                        
                        redundant_ku = knowledge_unit_list[redundant_index]
                        primary_ku = knowledge_unit_list[primary_index]
                        
                        if primary_ku and 'v_f' in primary_ku and primary_ku['v_f']:
                            redundant_ku['v_f'] = primary_ku['v_f'].copy()
                            cleaned_count += 1
                            logging.info(f"Unified temp VF content: {redundant_id} -> {primary_id}")
                except (ValueError, IndexError) as e:
                    logging.error(f"Error processing temp VF: {redundant_id}, error: {e}")

            logging.info(f"VF redundancy: replaced {len(temp_to_permanent)} temp VFs with permanent VFs, unified {len(remaining_temp_mapping)} temp VF pairs")
            
    except Exception as e:
        logging.error(f"Failed to parse and clean vf redundancy: {e}")