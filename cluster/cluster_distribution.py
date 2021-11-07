import numpy as np
from fairseq.data import Dictionary
import tqdm
import pandas as pd
from scipy.sparse import csr_matrix
from scipy import sparse

dstore_size = 153225485

dists = np.load('checkpoints/wikitext103-bpe/dist.npy')
centroid_ids = np.load('checkpoints/wikitext103-bpe/centroid_ids.npy')
dictionary = Dictionary.load('data-bin/wikitext103-bpe/dict.txt')

# vals_from_memmap = np.memmap('checkpoints/wikitext103-bpe/dstore_vals.npy',
#                              dtype=np.int, mode='r', shape=(dstore_size, 1))
#
# vals = np.zeros((dstore_size, 1), dtype=np.int)
#
# vals[:] = vals_from_memmap[:]
# del vals_from_memmap
#
# vals = vals.squeeze()
#
# # after first zero it's all useless vecs
# first_zero_idx = (vals == 0).argmax(axis=0)
# vals = vals[:first_zero_idx]

# freq_mat = np.zeros((np.max(centroid_ids) + 1, len(dictionary)))
#
# for centroid_id, word_id in tqdm.tqdm(zip(centroid_ids, vals)):
#     freq_mat[centroid_id, word_id] += 1
#
# freq_mat = csr_matrix(freq_mat)
freq_mat = sparse.load_npz('checkpoints/wikitext103-bpe/cluster_count.npz')

print('Sparsity:', 1 - freq_mat.getnnz() / np.prod(freq_mat.shape))

cluster_size = csr_matrix.sum(freq_mat, axis=1)
cluster_size = np.squeeze(np.asarray(cluster_size), axis=1)

sums = np.repeat(cluster_size, freq_mat.getnnz(axis=1))
freq_mat.data /= sums

sparse.save_npz('checkpoints/wikitext103-bpe/cluster_freq.npz', freq_mat)

k = 10

data = []
for idx in tqdm.tqdm(range(freq_mat.shape[0])):
    row = freq_mat.getrow(idx).toarray()[0].ravel()
    top_k_indices = row.argsort()[-k:][::-1]
    top_k_values = row[top_k_indices]
    item = {'cluster_id': idx,
            'count': cluster_size[idx],
            }
    for j in range(k):
        assert top_k_indices[j] < len(dictionary)
        item['word'+str(j)] = dictionary[top_k_indices[j]]
        item['freq'+str(j)] = top_k_values[j]

    data.append(item)

df = pd.DataFrame(data)
df.to_csv('cluster.csv')
