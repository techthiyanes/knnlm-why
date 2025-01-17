import math
from tqdm import tqdm

import numpy as np
import torch

from fairseq.data import Dictionary

dictionary = Dictionary.load('data-bin/wikitext103-bpe/dict.txt')
print(len(dictionary))

bpe_cont = "@@"
bpe_toks = {
    i
    for i in range(len(dictionary))
    if dictionary[i].endswith(bpe_cont)
}

bpe_len = len(bpe_cont)

tokens = np.load('tokens.npy')
lm_scores = np.load('scores.npy')
knn_scores = np.load('best_knn_only_scores.npy')

assert len(tokens) == len(lm_scores)
assert len(knn_scores) == len(tokens)

lm_scores = torch.from_numpy(lm_scores).cuda()
tgt_len = tokens.size
skipped_toks = 0
for i in range(tgt_len - 1):
    if tokens[i].item() in bpe_toks:
        skipped_toks += 1

count = len(tokens) - skipped_toks

knn_helping = 0
with open('overfit_interpolation_epoch.txt', 'w') as outfile:
    for epoch in tqdm(range(234)):
        if epoch == 0:
            overfit_scores = np.load('best_knn_only_scores.npy')
        else:
            overfit_scores = np.load('overfit_scores/overfit_lm_scores_checkpoint{}.npy'.format(epoch))
        overfit_scores = torch.from_numpy(overfit_scores).cuda()
        combine_probs = torch.stack([lm_scores, overfit_scores], dim=0)

        oracle_scores, argmaxs = torch.max(combine_probs, dim=0)

        oracle_ppl = torch.exp(-oracle_scores.sum() / count)

        if epoch == 0:
            knn_helping = argmaxs

        match_knn = torch.sum(argmaxs == knn_helping).item() / len(tokens)

        knn_helping_scores = -(combine_probs[0][knn_helping == 0].sum() + combine_probs[1][knn_helping == 1].sum())
        knn_helping_ppl = torch.exp(knn_helping_scores / count)

        best_ppl = 1e10
        best_lmbda = 0
        for lmbda in np.linspace(0.0, 0.999, num=200):
            coeffs = torch.ones_like(combine_probs)
            coeffs[0] = np.log(1 - lmbda)
            coeffs[1] = np.log(lmbda)

            scores = torch.logsumexp(combine_probs + coeffs, dim=0)

            score_sum = scores.sum()

            avg_nll_loss = -score_sum / count / math.log(2)  # convert to base 2
            ppl = 2 ** avg_nll_loss.item()
            if ppl < best_ppl:
                best_ppl = ppl
                best_lmbda = lmbda

        outfile.write('{}\t{}\t{}\t{}\t{}\t{}\n'.format(epoch, best_lmbda, best_ppl, oracle_ppl, match_knn, knn_helping_ppl))
