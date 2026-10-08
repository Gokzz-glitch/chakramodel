import numpy as np

class FLNonIIDPartitioner:
    """
    Partitions datasets (e.g., Kvasir, ClinicDB) to simulate extreme Non-IID (Independent and Identically Distributed)
    environments for Federated Learning (C5).
    This proves that the CoAtNet+FedAvg architecture remains robust even when hospitals have highly skewed data.
    """
    
    @staticmethod
    def partition_dirichlet(dataset_indices, labels, num_clients=3, alpha=0.5):
        """
        Partitions the dataset into `num_clients` subsets based on a Dirichlet distribution.
        alpha: Concentration parameter. Lower alpha -> higher Non-IID (more skewed).
        """
        num_classes = len(np.unique(labels))
        
        # Output is a list of lists of indices for each client
        client_indices = [[] for _ in range(num_clients)]
        
        for k in range(num_classes):
            # Find all indices for this class
            class_indices = np.where(labels == k)[0]
            np.random.shuffle(class_indices)
            
            # Sample from Dirichlet distribution to get proportions for this class across clients
            proportions = np.random.dirichlet(np.repeat(alpha, num_clients))
            
            # Balance out the proportions to avoid completely empty assignments
            proportions = np.array([p * (len(client_idx) < len(dataset_indices) / num_clients) 
                                  for p, client_idx in zip(proportions, client_indices)])
            proportions = proportions / proportions.sum()
            
            # Split class indices based on proportions
            split_points = (np.cumsum(proportions) * len(class_indices)).astype(int)[:-1]
            splits = np.split(class_indices, split_points)
            
            for client_id, split in enumerate(splits):
                client_indices[client_id].extend(dataset_indices[split])
                
        # Shuffle indices within each client
        for idx in client_indices:
            np.random.shuffle(idx)
            
        return client_indices

if __name__ == "__main__":
    print("Testing FL Non-IID Dirichlet Partitioner...")
    
    # Simulate a dataset of 1000 images with 2 classes (e.g., small polyp vs large polyp)
    num_samples = 1000
    indices = np.arange(num_samples)
    
    # 70% class 0, 30% class 1
    mock_labels = np.array([0] * 700 + [1] * 300)
    
    # Extreme Non-IID (alpha = 0.1)
    print("\nAlpha = 0.1 (Extreme Non-IID):")
    client_splits = FLNonIIDPartitioner.partition_dirichlet(indices, mock_labels, num_clients=3, alpha=0.1)
    
    for i, split in enumerate(client_splits):
        labels_in_split = mock_labels[split]
        count_0 = np.sum(labels_in_split == 0)
        count_1 = np.sum(labels_in_split == 1)
        print(f"Client {i+1}: Total={len(split)}, Class 0={count_0}, Class 1={count_1}")
        
    # Mild Non-IID (alpha = 10.0)
    print("\nAlpha = 10.0 (Near IID):")
    client_splits = FLNonIIDPartitioner.partition_dirichlet(indices, mock_labels, num_clients=3, alpha=10.0)
    
    for i, split in enumerate(client_splits):
        labels_in_split = mock_labels[split]
        count_0 = np.sum(labels_in_split == 0)
        count_1 = np.sum(labels_in_split == 1)
        print(f"Client {i+1}: Total={len(split)}, Class 0={count_0}, Class 1={count_1}")
