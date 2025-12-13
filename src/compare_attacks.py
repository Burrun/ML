import csv
import numpy as np
import os
import glob

def get_newest_prediction_file(directory):
    """Find the newest *_predictions.csv file in the given directory."""
    files = glob.glob(os.path.join(directory, "*_predictions.csv"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def load_predictions(filepath):
    """Load predictions from CSV. Returns a dict mapping filename to (true_label, predicted_label, prob_malware)."""
    preds = {}
    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = os.path.basename(row['file_path'])
                # Remove "adv_" prefix if present
                if filename.startswith("adv_"):
                    filename = filename[4:]
                
                preds[filename] = {
                    'true_label': int(row['true_label']),
                    'predicted_label': int(row['predicted_label']),
                    'prob_malware': float(row['prob_malware'])
                }
        return preds
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def calculate_metrics(base_preds, target_preds):
    """Calculate evasion rate and score drops."""
    common_files = set(base_preds.keys()) & set(target_preds.keys())
    
    malware_files = []
    for f in common_files:
        if base_preds[f]['true_label'] == 1: # Only consider malware
            malware_files.append(f)
            
    if not malware_files:
        return None

    # Evasion Rate: Percentage of malware predicted as benign (0) in target
    evaded_count = 0
    reductions = []
    base_scores = []
    
    for f in malware_files:
        # Evasion check
        if target_preds[f]['predicted_label'] == 0:
            evaded_count += 1
            
        # Score drop
        base_score = base_preds[f]['prob_malware']
        target_score = target_preds[f]['prob_malware']
        reductions.append(base_score - target_score)
        base_scores.append(base_score)
        
    evasion_rate = (evaded_count / len(malware_files)) * 100
    
    reductions = np.array(reductions)
    base_scores = np.array(base_scores)
    
    # Average Score Drop
    avg_drop = np.mean(reductions)
    
    # P10-P90 Score Drop
    p10 = np.percentile(base_scores, 10)
    p90 = np.percentile(base_scores, 90)
    
    mask = (base_scores >= p10) & (base_scores <= p90)
    trimmed_reductions = reductions[mask]
    
    if len(trimmed_reductions) > 0:
        avg_drop_trimmed = np.mean(trimmed_reductions)
    else:
        avg_drop_trimmed = 0.0
        
    return {
        'evasion_rate': evasion_rate,
        'avg_drop': avg_drop,
        'avg_drop_trimmed': avg_drop_trimmed,
        'count': len(malware_files)
    }

def main():
    # 1. Base Directory (Origin)
    base_dir = "data/output"
    base_file = get_newest_prediction_file(base_dir)
    
    if not base_file:
        print(f"❌ Error: No prediction file found in {base_dir}")
        return

    print(f"✅ Base File: {base_file}")
    base_preds = load_predictions(base_file)
    
    # 2. Attack Directories
    attack_dirs = [
        "TEST/ExtendDOS/output",
        "TEST/Header/output",
        "TEST/Kreuk/output",
        "TEST/Padding/output",
        "TEST/Slack/output"
    ]
    
    results = []
    
    for d in attack_dirs:
        if not os.path.exists(d):
            continue
            
        target_file = get_newest_prediction_file(d)
        if not target_file:
            continue
            
        method_name = d.split("/")[1] # TEST/ExtendDOS/output -> ExtendDOS
        target_preds = load_predictions(target_file)
        
        metrics = calculate_metrics(base_preds, target_preds)
        
        if metrics:
            results.append({
                'Method': method_name,
                'File': os.path.basename(target_file),
                **metrics
            })

    # 3. Print Results
    print("\n### Attack Effectiveness Analysis")
    print(f"Base: {os.path.basename(base_file)}")
    print("\n| Method | Evasion Rate (%) | Avg Score Drop | Avg Score Drop (P10~P90) |")
    print("| :--- | :--- | :--- | :--- |")
    
    for r in results:
        print(f"| **{r['Method']}** | {r['evasion_rate']:.2f}% | {r['avg_drop']:.6f} | {r['avg_drop_trimmed']:.6f} |")

if __name__ == "__main__":
    main()
