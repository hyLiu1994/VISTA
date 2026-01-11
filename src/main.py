import os
import sys
import logging
from utils.HyperParameters import configure_parser
from utils.Evaluation import evaluate_imputed_result
from utils.utils import setup_logging
from data.AISDataProcess import get_training_test_data
from pipeline.pipeline import SDKG_Construction_Multithreading,Trajectory_Imputation_Multithreading
from modules.M0_SDKG import SDKG
from modules.M7_Scheduler import KnowledgeUnitManager,ImputationResultsManager

# root path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def pipline_VISTA_Multithreading(args):
    setup_logging(args)

    #Get Training and Testing Data
    _ , (test_df, mark_missing_test) = get_training_test_data(args)
    logging.warning(f"mark_missing_test:{mark_missing_test}")
    # Building SDKG
    sdkg = SDKG(args)
    ku_manager = KnowledgeUnitManager(args)
    result_manager=ImputationResultsManager(args)
    
    sdkg.load_SDKG(args.end_point_sdkg)
    ku_manager.load_knowledge_unit_list(args.end_point_sdkg)
   
    if((not sdkg.SDK_graph_vs) or (not ku_manager.knowledge_unit_list)):
        sdkg, ku_manager = SDKG_Construction_Multithreading(
            args=args,
            trajectory_data = (test_df, mark_missing_test),
            ku_manager = ku_manager,
            SDKG = sdkg,
        )    
    else : 
        logging.info(f"SDKG and KnowledgeUnitList loaded up to checkpoint {args.end_point_sdkg}, skipping Update_SDKG.")
    #Trajectory imputation
    result_manager.load_results_list(args.end_point_sdkg,args)
    if(not result_manager.results_list):
        result_manager = Trajectory_Imputation_Multithreading(
            args=args,
            trajectory_data = (test_df, mark_missing_test),
            context_info_manager = ku_manager,
            SDKG = sdkg,
            result_manager=result_manager
        ) 
    else : 
        logging.info(f"Result Manager loaded up to checkpoint {args.end_point_sdkg}, skipping imputate_missing_segments.")

    # evaluate the imputed result
    evaluate_imputed_result(args, result_manager, test_df, mark_missing_test,sdkg)

if __name__ == "__main__":
    experiment_parser = configure_parser()
    print("experiment_parser:", experiment_parser)
    pipline_VISTA_Multithreading(experiment_parser.parse_args())