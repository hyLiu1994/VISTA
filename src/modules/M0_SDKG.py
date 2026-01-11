import os
import json
import re
import logging
from src.utils.HyperParameters import root_path
class SDKG:
    def __init__(self, args):
        self.base_dir =  root_path + '/results/' + args.exp_name + '/SDKG/'
        os.makedirs(self.base_dir, exist_ok=True)
        self.speed_dict = {} 
        self.course_dict = {}
        self.heading_dict = {}
        self.intent_dict = {}
        self.duration_dict = {}

        # self.SDK_graph_vs["attribute_id"]["attribute_value"][vb_id] = weight
        self.SDK_graph_vs = {}

        # self.SDK_graph_vb["vb_id"]["vs_id"/"vf_id"] = weight
        # self.SDK_graph_vb_node["vb_id"] = {
        #     "speed_pattern": xxx,
        #     "course_pattern": xxx,
        #     "heading_pattern": xxx,
        #     "intent_pattern": xxx,
        #     "duration_pattern": xxx,
        # }
        self.SDK_graph_vb = {}
        self.SDK_graph_vb_node = {}
        # self.SDK_graph_vf["vf_id"]["vb_id"] = weight
        # self.SDK_graph_vf_node["vf_id"] = {
        #     "description": xxx,
        #     "code": xxx,
        # }
        self.SDK_graph_vf = {}
        self.SDK_graph_vf_node = {}
        
    def update_dicts(self, v_b):
        new_flags = {
            "speed_profile": False,
            "course_change": False, 
            "heading_fluctuation": False,
            "intent": False
        }
        
        for key, value in v_b.items():
            #clean_value = re.sub(r'\s*\(.*\)', '', value).strip()
            clean_value = re.split(r'[(:]', str(value), 1)[0].strip()
            
            if key == "speed_profile":
                if clean_value not in self.speed_dict:
                    self.speed_dict[clean_value] = True
                    new_flags["speed_profile"] = True
            elif key == "course_change":
                if clean_value not in self.course_dict:
                    self.course_dict[clean_value] = True
                    new_flags["course_change"] = True
            elif key == "heading_fluctuation":
                if clean_value not in self.heading_dict:
                    self.heading_dict[clean_value] = True
                    new_flags["heading_fluctuation"] = True
            elif key == "intent":
                if clean_value not in self.intent_dict:
                    self.intent_dict[clean_value] = True
                    new_flags["intent"] = True

        updated_categories = [category for category, is_new in new_flags.items() if is_new]
        if updated_categories:
            logging.info(f"New pattern values added in categories: {updated_categories}")
        
        return new_flags
    
    def clean_dicts(self, attribute_redundancy):
        total_cleaned = 0

        dict_mapping = {
            "speed_profile": self.speed_dict,
            "course_change": self.course_dict,
            "heading_fluctuation": self.heading_dict,
            "intent": self.intent_dict
        }

        for attribute, redundancy_mapping in attribute_redundancy.items():
            if attribute in dict_mapping:
                target_dict = dict_mapping[attribute]
                
                for redundant_term, primary_term in redundancy_mapping.items():
                    
                    if redundant_term in target_dict:
                        
                        if primary_term not in target_dict:
                            target_dict[primary_term] = True
        
                        del target_dict[redundant_term]
                        total_cleaned += 1
                        logging.info(f"SDKG cleaned {attribute}: '{redundant_term}' -> '{primary_term}'")
        
        logging.info(f"SDKG pattern dictionaries: cleaned {total_cleaned} redundant terms")
        return total_cleaned
    
    def check_vf_exists(self, vf_id):
        return vf_id in self.SDK_graph_vf_node

    def find_vb_attribute(self, vb_id):
        return self.SDK_graph_vb_node[vb_id]
    
    def load_vf_node(self):
        return self.SDK_graph_vf_node
    
    def merge_vf_nodes(self, target_vf_id, source_vf_id):
    
        if source_vf_id not in self.SDK_graph_vf_node:
            logging.warning(f"Source VF node {source_vf_id} not found")
            return False
            
        if target_vf_id not in self.SDK_graph_vf_node:
            logging.warning(f"Target VF node {target_vf_id} not found")
            return False
        
        logging.info(f"Merging VF node {source_vf_id} into {target_vf_id}")
        
        if source_vf_id in self.SDK_graph_vf:
            source_vb_connections = self.SDK_graph_vf[source_vf_id]
            
            for vb_id, weight in source_vb_connections.items():
                if vb_id in self.SDK_graph_vf[target_vf_id]:
                    self.SDK_graph_vf[target_vf_id][vb_id] += weight
                else:
                    self.SDK_graph_vf[target_vf_id][vb_id] = weight
                
                if vb_id in self.SDK_graph_vb:
                    if source_vf_id in self.SDK_graph_vb[vb_id]:
                        source_weight = self.SDK_graph_vb[vb_id][source_vf_id]
                        
                        if target_vf_id in self.SDK_graph_vb[vb_id]:
                            self.SDK_graph_vb[vb_id][target_vf_id] += source_weight
                        else:
                            self.SDK_graph_vb[vb_id][target_vf_id] = source_weight

                        del self.SDK_graph_vb[vb_id][source_vf_id]
        
        if source_vf_id in self.SDK_graph_vf:
            del self.SDK_graph_vf[source_vf_id]

        del self.SDK_graph_vf_node[source_vf_id]
        
        logging.info(f"Successfully merged {source_vf_id} into {target_vf_id}")
        return True
    def select_Cb(self, args, Vs_list):
        """
        Returns:
            Cb: ([vb_id1, vb_id2, ...], [vb_node1, vb_node2, ...])
        """
        all_attributes = {}
        for vs in Vs_list:
            if not vs:
                continue
            for attr_name, attr_value in vs.items():
                if attr_name in ['block', 'seq', 'MMSI']:
                    continue
                if attr_name not in all_attributes:
                    all_attributes[attr_name] = set()
                all_attributes[attr_name].add(attr_value)
        
        candidate_vbs = {} 
        
        for attr_name, attr_values in all_attributes.items():
            for attr_value in attr_values:
                if (attr_name in self.SDK_graph_vs and 
                    attr_value in self.SDK_graph_vs[attr_name]):
                    weight_map = self.SDK_graph_vs[attr_name][attr_value]  
                    for vb_id, weight in weight_map.items():
                        if vb_id not in candidate_vbs:
                            candidate_vbs[vb_id] = 1.0
                        candidate_vbs[vb_id] *= (float(weight) + 1.0)
        
        if not candidate_vbs:
            return ([], [])
        
        total_support = sum(candidate_vbs.values())
        vb_scores = []
        
        for vb_id, product_support in candidate_vbs.items():
            normalized_score = product_support / total_support
            vb_scores.append((vb_id, normalized_score))

        vb_scores.sort(key=lambda x: x[1], reverse=True)
        top_vb_ids = [vb_id for vb_id, score in vb_scores[:args.top_k]]

        top_vb_nodes = []
        for vb_id in top_vb_ids:
            if vb_id in self.SDK_graph_vb_node:
                top_vb_nodes.append(self.SDK_graph_vb_node[vb_id])
            else:
                top_vb_nodes.append({"vb_id": vb_id, "error": "node not found"})
        #logging.info(f"Selected top {len(top_vb_ids)} vb_ids: {top_vb_ids}")
        return (top_vb_ids, top_vb_nodes)
    
    def select_Cf_Cb(self, args, Cb):
        """
        Returns:
            Cf: ([vf_id1, vf_id2, ...], [vf_node1, vf_node2, ...])
        """
        vb_ids, _ = Cb  
        
        if not vb_ids:
            return ([], [])
        
        candidate_vfs = {} 
        
        for vb_id in vb_ids:
            if vb_id in self.SDK_graph_vb:
                vf_weight_map = {}
                for connected_id, weight in self.SDK_graph_vb[vb_id].items():
                    if isinstance(connected_id, str) and connected_id.startswith('vf_'):
                        vf_weight_map[connected_id] = weight
                
                for vf_id, weight in vf_weight_map.items():
                    if vf_id not in candidate_vfs:
                        candidate_vfs[vf_id] = 1.0
                    candidate_vfs[vf_id] *= (float(weight) + 1.0)

        if not candidate_vfs:
            return ([], [])
        
        total_support = sum(candidate_vfs.values())
        vf_scores = []
        
        for vf_id, product_support in candidate_vfs.items():
            normalized_score = product_support / total_support
            vf_scores.append((vf_id, normalized_score))
        
        vf_scores.sort(key=lambda x: x[1], reverse=True)
        top_vf_ids = [vf_id for vf_id, score in vf_scores[:args.top_k]]
        
        top_vf_nodes = []
        for vf_id in top_vf_ids:
            if vf_id in self.SDK_graph_vf_node:
                top_vf_nodes.append(self.SDK_graph_vf_node[vf_id])
            else:
                top_vf_nodes.append({"vf_id": vf_id, "error": "node not found"})
        
        return (top_vf_ids, top_vf_nodes)

    def generate_induce_graph(self, Vs, Cb, Cf):
        """
        Graph description string in DOT format
        """
        nodes = []
        edges = []
        
        if Vs:
            for vs in Vs:
                if not vs:
                    continue
                for attr_name, attr_value in vs.items():
                    if attr_name not in ['block', 'seq', 'MMSI']:
                        node_id = f"vs_{attr_name}_{attr_value}"
                        label = f"Static Attribute\\n{attr_name}: {attr_value}"
                        nodes.append(f'  {node_id} [label="{label}"];')
                
        if Cb:
                vb_ids, vb_nodes = Cb
                for vb_id in vb_ids:
                    if vb_id in self.SDK_graph_vb_node:
                        vb_node = self.SDK_graph_vb_node[vb_id]
                        label_parts = []
                        for key in ["speed_profile", "course_change", "heading_fluctuation", "intent", "duration"]:
                            if key in vb_node:
                                label_parts.append(f"{key}: {vb_node[key]}")
                        label = "Behavior Pattern\\n" + "\\n".join(label_parts)
                        nodes.append(f'  {vb_id} [label="{label}"];')

                    if Vs:
                        for vs in Vs:
                            if not vs:
                                continue
                            for attr_name, attr_value in vs.items():
                                if attr_name not in ['block', 'seq', 'MMSI']:
                                    vs_id = f"vs_{attr_name}_{attr_value}"
                                    if (attr_name in self.SDK_graph_vs and 
                                        attr_value in self.SDK_graph_vs[attr_name] and
                                        vb_id in self.SDK_graph_vs[attr_name][attr_value]):
                                        weight = self.SDK_graph_vs[attr_name][attr_value][vb_id]
                                        if weight > 0:
                                            edges.append(f'  {vs_id} -> {vb_id} [label="w={weight}"];')
        if Cf:
            vf_ids, vf_nodes = Cf  
            for vf_id in vf_ids:
                if vf_id in self.SDK_graph_vf_node:
                    vf_node = self.SDK_graph_vf_node[vf_id]
                    desc = vf_node.get("description", "")
                    label = f"Function\\n{desc}"
                    nodes.append(f'  {vf_id} [label="{label}"];')

                    if Cb:
                        vb_ids, _ = Cb 
                        for vb_id in vb_ids:
                            if (vb_id in self.SDK_graph_vb and 
                                vf_id in self.SDK_graph_vb[vb_id]):
                                weight = self.SDK_graph_vb[vb_id][vf_id]
                                edges.append(f'  {vb_id} -> {vf_id} [label="w={weight}"];')

        dot_lines = ["digraph InducedSubgraph {", "  rankdir=LR;"]
        dot_lines.extend(nodes)
        dot_lines.extend(edges)
        dot_lines.append("}")
        #logging.info("Generated DOT graph:\n" + "\n".join(dot_lines))
        return "\n".join(dot_lines)

    def select_Cf_vb(self, vb):
        core_attributes = ["speed_profile", "course_change", "heading_fluctuation", "intent", "duration"]
        vb_hash_content = {}
        
        for attr in core_attributes:
            if attr in vb:
                clean_value = re.split(r'[(:]', str(vb[attr]), 1)[0].strip()
                vb_hash_content[attr] = clean_value
        
        vb_content_str = json.dumps(vb_hash_content, sort_keys=True)
        vb_hash = hash(vb_content_str)
        vb_id = f"vb_{vb_hash}"
        
        if vb_id in self.SDK_graph_vb_node:
            vb_connections = self.SDK_graph_vb.get(vb_id, {})
            max_weight = 0
            best_vf_id = None
            
            for connected_id, weight in vb_connections.items():
                if isinstance(connected_id, str) and connected_id.startswith('vf_'):
                    if weight > max_weight:
                        max_weight = weight
                        best_vf_id = connected_id
            
            if best_vf_id:
                return self.SDK_graph_vf_node.get(best_vf_id)
        
        return None
    
    def update_SDK_graph(self, knowledge_unit):   
        if not knowledge_unit: 
            return
            
        v_s = knowledge_unit.get("v_s", {})
        v_b = knowledge_unit.get("v_b", {})
        v_f = knowledge_unit.get("v_f", {})
        
        if not v_b:
            return
            
        core_attributes = ["speed_profile", "course_change", "heading_fluctuation", "intent", "duration"]
        vb_hash_content = {}
        vb_storage_content = {}
        
        for attr in core_attributes:
            if attr in v_b:
                clean_value = re.split(r'[(:]', str(v_b[attr]), 1)[0].strip()
                vb_hash_content[attr] = clean_value
                vb_storage_content[attr] = str(v_b[attr]).strip()

        vb_content_str = json.dumps(vb_hash_content, sort_keys=True)
        vb_hash = hash(vb_content_str)
        vb_id = f"vb_{vb_hash}"

        if vb_id not in self.SDK_graph_vb_node:
            storage_attributes = {}
            for attr in core_attributes:
                if attr in vb_storage_content:
                    storage_attributes[attr] = vb_storage_content[attr]
                else:
                    storage_attributes[attr] = "unknown"
            
            self.SDK_graph_vb_node[vb_id] = {
                "speed_profile": storage_attributes["speed_profile"],
                "course_change": storage_attributes["course_change"], 
                "heading_fluctuation": storage_attributes["heading_fluctuation"],
                "intent": storage_attributes["intent"],
                "duration": storage_attributes["duration"],
                "llm_output": v_b.get("llm_output", "")  
            }
            self.SDK_graph_vb[vb_id] = {}

        if v_s:
            for attr_name, attr_value in v_s.items():
                if attr_name in ['block', 'seq', 'MMSI']:
                    continue
                if attr_name not in self.SDK_graph_vs:
                    self.SDK_graph_vs[attr_name] = {}
                
                if attr_value not in self.SDK_graph_vs[attr_name]:
                    self.SDK_graph_vs[attr_name][attr_value] = {}

                if vb_id in self.SDK_graph_vs[attr_name][attr_value]:
                    self.SDK_graph_vs[attr_name][attr_value][vb_id] += 1
                else:
                    self.SDK_graph_vs[attr_name][attr_value][vb_id] = 1
                    
                vs_key = f"vs_{attr_name}_{attr_value}"  
                if vs_key in self.SDK_graph_vb[vb_id]:
                    self.SDK_graph_vb[vb_id][vs_key] += 1
                else:
                    self.SDK_graph_vb[vb_id][vs_key] = 1
        
        if v_f:
            func_content = v_f.get('spatial_function', '').strip()
            vf_hash = hash(func_content)
            vf_id = f"vf_{vf_hash}"
            
            if vf_id not in self.SDK_graph_vf_node:
                self.SDK_graph_vf_node[vf_id] = {
                    "description": v_f.get("describe_of_function", ""), 
                    "code": v_f.get("spatial_function", "") 
                }
                self.SDK_graph_vf[vf_id] = {}

            if vb_id in self.SDK_graph_vf[vf_id]:
                self.SDK_graph_vf[vf_id][vb_id] += 1
            else:
                self.SDK_graph_vf[vf_id][vb_id] = 1
            
            if vf_id in self.SDK_graph_vb[vb_id]:
                self.SDK_graph_vb[vb_id][vf_id] += 1
            else:
                self.SDK_graph_vb[vb_id][vf_id] = 1

        logging.info("Updated SDK graph with new knowledge unit")

    def update_SDK_graph_per_batch(self, knowledge_unit_list):
        if not knowledge_unit_list:
            return
        
        for knowledge_unit in knowledge_unit_list:
            self.update_SDK_graph(knowledge_unit)
        logging.info("Updated SDK graph with batch of knowledge units")

    
    def get_vb_attributes_dicts(self):
        return {
            "speed_dict": self.speed_dict,
            "course_dict": self.course_dict,
            "heading_dict": self.heading_dict, 
            "intent_dict": self.intent_dict
        }
        
    def save_SDKG(self, checkpoint_point):
        logging.info(f"Saving SDKG to {os.path.join(self.base_dir, 'pattern_attributes_dicts_' + checkpoint_point + '.json')}")
        def convert_keys(obj):
            if isinstance(obj, dict):
                return {str(k): convert_keys(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_keys(item) for item in obj]
            else:
                return obj
        with open(os.path.join(self.base_dir, "pattern_attributes_dicts_" + checkpoint_point + ".json"), "w") as f:
            json.dump({"speed_dict": self.speed_dict, "course_dict": self.course_dict, "heading_dict": self.heading_dict, "intent_dict": self.intent_dict}, f, indent=2)

        with open(os.path.join(self.base_dir, "SDK_graph_vs_" + checkpoint_point + ".json"), "w") as f:
                json.dump({"SDK_graph_vs": convert_keys(self.SDK_graph_vs)}, f, indent=2)  

        with open(os.path.join(self.base_dir, "SDK_graph_vb_" + checkpoint_point + ".json"), "w") as f:
            json.dump({"SDK_graph_vb": convert_keys(self.SDK_graph_vb)}, f, indent=2) 
        
        with open(os.path.join(self.base_dir, "SDK_graph_vb_node_" + checkpoint_point + ".json"), "w") as f:
            json.dump({"SDK_graph_vb_node": convert_keys(self.SDK_graph_vb_node)}, f, indent=2) 

        with open(os.path.join(self.base_dir, "SDK_graph_vf_" + checkpoint_point + ".json"), "w") as f:
            json.dump({"SDK_graph_vf": convert_keys(self.SDK_graph_vf)}, f, indent=2) 

        with open(os.path.join(self.base_dir, "SDK_graph_vf_node_" + checkpoint_point + ".json"), "w") as f:
            json.dump({"SDK_graph_vf_node": convert_keys(self.SDK_graph_vf_node)}, f, indent=2)  
        return 

    def load_SDKG(self, start_point):
        if (start_point == 0):
            return

        logging.info(f"Loading SDKG from {os.path.join(self.base_dir, 'pattern_attributes_dicts_' + str(start_point) + '.json')}")
        dicts_file=os.path.join(self.base_dir, "pattern_attributes_dicts_" + str(start_point) + ".json")
        if os.path.exists(dicts_file):
            with open(dicts_file, "r") as f:
                dicts = json.load(f)
                self.speed_dict = dicts["speed_dict"]
                self.course_dict = dicts["course_dict"]
                self.heading_dict = dicts["heading_dict"]
                self.intent_dict = dicts["intent_dict"]
        else: 
            logging.info(f"pattern_attributes_dicts_{str(start_point)}.json not found")


        vs_file=os.path.join(self.base_dir, "SDK_graph_vs_" + str(start_point) + ".json")
        if os.path.exists(vs_file):
            with open(vs_file, "r") as f:
                self.SDK_graph_vs = json.load(f)["SDK_graph_vs"]
        else:
            logging.info(f"SDK_graph_vs_{str(start_point)}.json not found")


        vb_file=os.path.join(self.base_dir, "SDK_graph_vb_" + str(start_point) + ".json")
        if os.path.exists(vb_file):
            with open(vb_file, "r") as f:
                self.SDK_graph_vb = json.load(f)["SDK_graph_vb"]
        else:
            logging.info(f"SDK_graph_vb_{str(start_point)}.json not found")
  

        vf_file=os.path.join(self.base_dir, "SDK_graph_vf_" + str(start_point) + ".json")
        if os.path.exists(vf_file):
            with open(vf_file, "r") as f:
                self.SDK_graph_vf = json.load(f)["SDK_graph_vf"]
        else:
            logging.info(f"SDK_graph_vf_{str(start_point)}.json not found")

        
        vb_node_file=os.path.join(self.base_dir, "SDK_graph_vb_node_" + str(start_point) + ".json")
        if os.path.exists(vb_node_file):
            with open(vb_node_file, "r") as f:
                self.SDK_graph_vb_node = json.load(f)["SDK_graph_vb_node"]
        else:
            logging.info(f"SDK_graph_vb_node_{str(start_point)}.json not found")


        vf_node_file=os.path.join(self.base_dir, "SDK_graph_vf_node_" + str(start_point) + ".json")
        if os.path.exists(vf_node_file):
            with open(vf_node_file, "r") as f:
                self.SDK_graph_vf_node = json.load(f)["SDK_graph_vf_node"]
        else:
            logging.info(f"SDK_graph_vf_node_{str(start_point)}.json not found")
 
