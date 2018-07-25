# -*- coding: utf-8 -*-

import os
import sys
import math
import random
import timeit
import argparse
import scipy.optimize as opt
from .lib.data_utils import Query, load_log
from collections import defaultdict, Counter



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='propensity estimation')
    parser.add_argument('--eta', default=1.0, type=float,
                        help='the parameter controls the severity of bias')
    parser.add_argument('-n', default=10, type=int,
        help='number of top positions for which estimates are desired')
    parser.add_argument('-a', '--approach', default='equitation',
                        choices=['naive', 'optimizer', 'equitation'])
    parser.add_argument('-m', '--method', default='TNC',
                        choices=['L-BFGS-B', 'TNC', 'SLSQP'])
    parser.add_argument('log_dir', help='click log dir')
    parser.add_argument('output_path', help='propensity result path')
    args = parser.parse_args()

    start = timeit.default_timer()

    M = args.n
    log0_path = os.path.join(args.log_dir, 'log0.txt')
    log1_path = os.path.join(args.log_dir, 'log1.txt')
    log0 = load_log(log0_path)
    log1 = load_log(log1_path)

    S = defaultdict(set)
    for q0, q1 in zip(log0, log1):
        assert q0._qid == q1._qid
        qid = q0._qid
        docs0 = q0._docs
        docs1 = q1._docs
        for rk0, doc0 in enumerate(docs0, start=1):
            if rk0 > M:
                break
            doc_id0, _ = doc0
            for rk1, doc1 in enumerate(docs1, start=1):
                if rk1 > M:
                    break
                if rk1 == rk0:
                    continue
                doc_id1, _ = doc1
                if doc_id1 == doc_id0:
                    S[(rk0, rk1)].add((qid, doc_id0))
                    S[(rk1, rk0)].add((qid, doc_id0))
                    break

    n0 = len(log0)
    n1 = len(log1)
    assert n0 == n1
    w = Counter()
    for q in log0:
        qid = q._qid
        docs = q._docs
        for rk, doc in enumerate(docs, start=1):
            if rk > M:
                break
            doc_id, _ = doc
            w.update({(qid, doc_id, rk):n0})
    for q in log1:
        qid = q._qid
        docs = q._docs
        for rk, doc in enumerate(docs, start=1):
            if rk > M:
                break
            doc_id, _ = doc
            w.update({(qid, doc_id, rk):n1})

    c = Counter()
    not_c = Counter()
    for q in log0:
        qid = q._qid
        docs = q._docs
        for rk, doc in enumerate(docs, start=1):
            if rk > M:
                break
            doc_id, delta = doc
            v = delta / w[(qid, doc_id, rk)]
            v_ = (1 - delta) / w[(qid, doc_id, rk)]
            for rk_ in range(1, M + 1):
                if (qid, doc_id) in S[(rk, rk_)]:
                    c.update({(rk, rk_): v})
                    not_c.update({(rk, rk_): v_})
    for q in log1:
        qid = q._qid
        docs = q._docs
        for rk, doc in enumerate(docs, start=1):
            if rk > M:
                break
            doc_id, delta = doc
            v = delta / w[(qid, doc_id, rk)]
            v_ = (1 - delta) / w[(qid, doc_id, rk)]
            for rk_ in range(1, M + 1):
                if (qid, doc_id) in S[(rk, rk_)]:
                    c.update({(rk, rk_): v})
                    not_c.update({(rk, rk_): v_})

    if args.approach == 'optimizer':
        def p_idx(k):
            return (k - 1) * M + k - 1

        def r_idx(k, k_):
            assert k != k_
            if k < k_:
                return (k - 1) * M + k_ - 1
            else:
                return (k_ - 1) * M + k - 1

        def likelihood(x):
            l = 0
            for k in range(2, M + 1):
                for k_ in range(2, M + 1):
                    if k != k_:
                        l += c[(k, k_)] * math.log(x[p_idx(k)] * x[r_idx(k, k_)])
                        l += not_c[(k, k_)] * math.log(1 - x[p_idx(k)] * x[r_idx(k, k_)])
            return -l

        a, b = 1e-4, 1-1e-4
        # x0 = [random.random() * (b - a) + a] * (M * M)
        x0 = [0.5] * (M * M)
        bnds = [(a, b)] * (M * M)

        ret = opt.minimize(likelihood, x0, method=args.method, bounds=bnds)
        xm = ret.x
        prop_ = [xm[p_idx(k)] / xm[p_idx(1)] for k in range(1, M + 1)]

    elif args.approach == 'naive':
        prop_ = [1]
        prop_.extend([c[(k,1)] / c[(1,k)] for k in range(2, M + 1)])
    elif args.approach == 'equitation':
        prop_ = [1]
        prop_.extend([c[(k,1)] * (c[(1,k)] + not_c[(1,k)]) /
            (c[(1,k)] * (c[(k,1)] + not_c[(k,1)])) for k in range(2, M + 1)])
    else:
        prop_ = [1] * M

    prop = [pow(k, -1 * args.eta) for k in range(1, M + 1)]
    with open(args.output_path, 'w') as fout:
        fout.write('p\tp_\n')
        for k in range(1, M + 1):
            fout.write('{:.3f}\t{:.3f}\n'.format(prop[k - 1], prop_[k - 1]))

    end = timeit.default_timer()
    print('Running time: {:.3}s.'.format(end - start))
