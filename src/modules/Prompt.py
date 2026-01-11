
USAGE_STAT = {
    "pattern":     {"prompt": 0, "completion": 0, "total": 0, "time_sec": 0.0, "calls": 0},
    "function":    {"prompt": 0, "completion": 0, "total": 0, "time_sec": 0.0, "calls": 0},
    "selection":   {"prompt": 0, "completion": 0, "total": 0, "time_sec": 0.0, "calls": 0},
    "explanation": {"prompt": 0, "completion": 0, "total": 0, "time_sec": 0.0, "calls": 0},
}

Pattern_Prompt= """[Task] 
You are an expert in maritime data analysis.
Your task is to generate a list of specific, interpretable patterns that describe how both **latitude and longitude** (vessel position) can be inferred from a set of AIS features.

These patterns will be used to **impute missing values of latitude and longitude** in AIS data. Each pattern must be:
- **Concrete and usable**, describing a clear condition on the target features and the corresponding position range;
- **Simultaneous**, including both latitude **and** longitude ranges, or describing a **trajectory pattern** (e.g., a curved path, straight line, or repeated loop);
- **Explainable**, with a short justification after each pattern explaining why this condition relates to the given position;
- **Mathematically expressive**, including a possible **trajectory equation or shape** that approximates the vessel's movement under this condition.

[INPUT]
You are given:
    A sample of trajectory data (latitude, longitude, and various AIS features):
    {trajectory_data}

[OUTPUT]
Please strictly follow the following format, return only one pattern,and output all patterns in triple quotes ''' ''':

'''
Pattern:
- **speed_pattern**: speed profile without numerical values and punctuation (detailed description for speed profile).
- **course_pattern**: change in course over ground without numerical values and punctuation (detailed description for change in course over ground).
- **heading_pattern**: heading fluctuation without numerical values and punctuation (detailed description for heading fluctuation).
- **intent**: inferred maneuver intention without numerical values and punctuation (detailed description for inferred maneuver intention).
'''

For speed_pattern, You can choose from {speed_dict}, and if you don't have a suitable one, you can create a new one. 
For course_pattern, You can choose from {course_dict}, and if you don't have a suitable one, you can create a new one. 
For heading_pattern, You can choose from {heading_dict}, and if you don't have a suitable one, you can create a new one. 
For intent,You can choose from {intent_dict}, and if you don't have a suitable one, you can create a new one. 

[EXAMPLE]
'''
Pattern:
- **speed_pattern**: stable (the vessel is maintaining a consistent speed, not accelerating or decelerating)
- **course_pattern**: stable (the vessel is maintaining a consistent course over ground)
- **heading_pattern**: stable (the heading does not fluctuate significantly, indicating no sharp maneuvers)
- **intent**: navigating (the vessel is maintaining its course)
'''
        
Make sure that your output strictly follows this format. Any patterns that do not adhere to this structure should be adjusted to fit the template. If any pattern involves multiple segments, please aggregate them as shown.
"""


Function_Prompt= """[Task] 
You are an expert in maritime trajectory analysis and spatial-temporal modeling, specialized in developing interpretable algorithms for vessel movement
reconstruction. You are given vessel trajectory data and are asked to generate a spatial_function that estimates missing latitude and longitude
positions based on known trajectory features and motion patterns.

[INPUT]
You are given by
- trajectory: 
    {combined_data}
- behavior pattern of trajectory:
    {pattern}

[OUTPUT]
The spatial_function should be a single-line, directly executable Python function. You are encouraged to choose from a variety of path models, not
just linear interpolation. It must compute a sequence of intermediate points using the provided start, end and Time_interval.    
- `start`: A tuple representing the geographic coordinates (latitude, longitude) immediately before the missing data block.
           Type: Tuple[float, float]
- `end`: A tuple representing the geographic coordinates (latitude, longitude) immediately after the missing data block.
         Type: Tuple[float, float]
- `Time_interval`: A list of time differences in seconds relative to the timestamp of the starting point, covering the entire range including the point before and after the missing block.
                   Type: List[float]
                
Please strictly follow the following format:
Function:''' def spatial_function(start, end, Time_interval): return [...] '''
Description:A brief explanation of what this function does, including how it uses the input parameters.

[Example]
'''def spatial_function(start, end, Time_interval): return []'''

{feedback_txt}
"""

Behavior_Estimator_Prompt="""
[TASK]
You are an expert maritime behavior analyst, specialized in interpreting vessel movement patterns and reasoning over graph-based representations
of AIS knowledge. You need to select the most plausible movement (behavior pattern) for the current gap. Specifically, the process is as follow:
    • Analyze the boundary movement patterns and DOT graph structure, then rely on their evidence weights to shortlist Top-{top_k} movements.
    • Choose ONE final movement ID for the gap.
    • Provide a two-part rationale:
    (1) Graph Support: cite the most informative vessel→movement edges (IDs/weights) that support your choice.
    (2) Contextual Justification: explain consistency with boundary movement patterns ($v_b^-$, $v_b^+$) and the gap's boundary conditions.
    • Output in the following block (no extra text):

[INPUT]
You are given by:
- Boundary movement patterns (behavior patterns extracted from adjacent segments on both sides of the missing block):
{boundary_text}
- Induced subgraph in DOT (vessel→movement and movement→function edges with weights):
{dot_text}
- Candidate movements (with tokens, graph priors and used edges): 
{movement_text}
- Contextual static attributes inferred from neighboring segments (vessel nodes):
{context_vessels}
- Incomplete AIS record sequence: 
{rows_text}


[OUTPUT]
Please strictly follow the following format:
'''
Selected Movement ID: <ID>
Graph Support: <edges and weights you rely on>
Contextual Justification: <why consistent with boundary context>
'''
"""


Method_Selector_Prompt = """
[TASK]
You are an expert in maritime spatial-temporal modeling and trajectory reconstruction, responsible for evaluating and selecting the most
suitable spatial function for accurate AIS trajectory imputation. Please select the most suitable spatial function for imputing missing latitude and
longitude.
You need to adhere following requirements:
• Direction: Which function has proven most reliable for similar kinematic patterns?
• Direction: Does the function's underlying model (e.g., linear, curved) logically match the identified movement pattern (e.g., curved, straight)?
• Direction: Which function works best across different but related movement patterns?
• Direction: How well does each function handle the specific speed/course/heading characteristics?
• Important: When providing Statistical Support, ONLY discuss statistical evidence — DO NOT mention any edge-weights and graph but you could
turn it to statistical describe.
• Important: Based on the calculation of weight proportions, all probabilities must be supported by evidence and cannot be arbitrarily fabricated.
Each probability should be followed by its calculation process.
• Important: Avoid repeating, movement pattern analysis — focus on function execution quality.

[INPUT]
You are given by
- Induced subgraph in DOT (Interpret weights as association frequencies.):
{dot_text}

**Functions with detailed information**:
{functions_text}

**behavior pattern that may correspond to missing parts**:
{movement_text}

**AIS samples to impute with it's context data**:
{rows_text}

[OUTPUT]
Please strictly follow the following format:
'''
Selected Function ID: <ID>
Statistical Support: <Don't describe the edge weight, Don't describe the graph support but you could turn it to statistical describe.1. Introduce the probability that this function can solve the missing value problem corresponding to the behavior pattern(Based on the calculation of weight proportions, all probabilities must be supported by evidence and cannot be arbitrarily fabricated. Each probability should be followed by its calculation process.).  
2. Introduce the characteristics of this function and its degree of matching with the current context.>
Reasoning: <why this function technically fits the kinematic requirements>
Imputation Action: <specific implementation details>
'''
"""


Explanation_Composer_Prompt = """
[TASK]
You are an expert in maritime behavior interpretation and regulatory reasoning, specialized in translating computational decisions into
human-understandable explanations for vessel trajectory analysis. Produce a human-friendly explanation for the chosen behavior and method. You
need to adhere following requirements:
• Do NOT mention any node IDs or labels such as “Movement_Pattern_*” or “vessel_*”.
• Refer ONLY to the concrete attributes and descriptions provided below.

[INPUT] You are given by:
- Induced subgraph in DOT:
{dot_text}

- Selected movement (expanded):
{movement_desc}

- Selected imputation method (expanded):
{function_desc}

- Contextual vessel attributes (expanded list):
{vessels_desc_block}

- Contextual behavior pattern:
{vessels_behavior_pattern}

[OUTPUT]
Please strictly follow the following format:
'''
Regulatory Rule Cue: <rule label + applicability + spatial anchor; leave Undetermined if insufficient>
Operational Protocol Rationale: <why this behavior is typical here; align with the spatial context; rule out key alternatives; do not mention IDs>
'''
"""

Redundancy_Analysis_Prompt = """
[TASK]
You are an expert in maritime knowledge consolidation and redundancy analysis, specializing in detecting and merging semantically equivalent
vessel behavior patterns and imputation functions. You need to adhere following requirements:
For BEHAVIOR PATTERNS:
- Exact duplicates: identical text
- Semantic equivalents: same meaning, different wording  
- Minor variations: slight wording differences
- Overly specific terms: very detailed descriptions
- Contextual synonyms: same meaning in maritime context

For SPATIAL FUNCTIONS:
- Functional equivalence: different implementations but same mathematical function
- Algorithmic similarity: same core algorithm with minor variations
- Parameter differences: same logic with different parameter values
- Code restructuring: same functionality with different code structure

[INPUT]
You are given by:
**BEHAVIOR PATTERNS TO ANALYZE**:
{vb_data_text}

**SPATIAL FUNCTIONS TO ANALYZE**:
{vf_data_text}

[OUTPUT]
Please strictly follow the following format:
For behavior patterns:
BEHAVIOR_REDUNDANCY:
[attribute_name]:
- <primary_term1> | [<redundant_term1>, <redundant_term2>]
- <primary_term2> | [<redundant_term3>, <redundant_term4>]
KEEP_UNIQUE: [<term1>, <term2>, <term3>]

For spatial functions:
FUNCTION_REDUNDANCY:
- <primary_function_id_or_code> | [<redundant_function_id_or_code1>, <redundant_function_id_or_code2>]
- <primary_function_id_or_code> | [<redundant_function_id_or_code3>]
KEEP_UNIQUE: [<function_id_or_code1>, <function_id_or_code2>]

Focus on maritime behavior semantics and functional equivalence. Preserve meaningful distinctions.
"""