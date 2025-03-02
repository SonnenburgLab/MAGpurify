#!/usr/bin/env python

import sys, Bio.Seq
from sklearn.decomposition import PCA
import numpy as np
import pandas as pd
from magpurify import utility
import argparse
import os

def fetch_args():
	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawTextHelpFormatter,
		usage=argparse.SUPPRESS,
		description="MAGpurify: tetra-freq module: find contigs with outlier tetranucleotide frequency"
	)
	parser.add_argument('program', help=argparse.SUPPRESS)
	parser.add_argument('fna', type=str,
		help="""Path to input genome in FASTA format""")
	parser.add_argument('out', type=str,
		help="""Output directory to store results and intermediate files""")
	parser.add_argument('-t', dest='threads', type=int, default=1,
		help="""Number of CPUs to use (default=1)""")
	parser.add_argument('-d', dest='db', type=str,
		help="""Path to reference database
By default, the MAGPURIFYDB environmental variable is used""")
	parser.add_argument('--cutoff', type=float, default=0.06,
		help="""Cutoff (default=0.06)""")
	args = vars(parser.parse_args())
	return args

def add_defaults(args):
	args['cutoff'] = 0.06

def init_kmers():
	tetra = {}
	for b1 in list('ACGT'):
		for b2 in list('ACGT'):
			for b3 in list('ACGT'):
				for b4 in list('ACGT'):
					kmer_fwd = ''.join([b1, b2, b3, b4])
					kmer_rev = str(Bio.Seq.Seq(kmer_fwd).reverse_complement())
					if kmer_fwd in tetra:
						continue
					elif kmer_rev in tetra:
						continue
					else:
						tetra[kmer_fwd] = 0
	return tetra

class Contig:
	def __init__(self):
		pass

def main():

	args = fetch_args()
	utility.add_tmp_dir(args)
	utility.check_input(args)
	utility.check_dependencies(['blastn'])
	utility.check_database(args)
	
	print("\n## Counting tetranucleotides")
	# init data
	kmer_counts = init_kmers()
	contigs = {}
	for rec in Bio.SeqIO.parse(args['fna'], 'fasta'):
		contig = Contig()
		contig.id = rec.id
		contig.seq = str(rec.seq)
		contig.kmers = kmer_counts.copy()
		contigs[rec.id] = contig

	# count kmers
	for contig in contigs.values():
		start, stop, step = 0, 4, 1
		while stop <= len(contig.seq):
			kmer_fwd = contig.seq[start:stop]
			kmer_rev = str(Bio.Seq.Seq(kmer_fwd).reverse_complement())
			if kmer_fwd in kmer_counts:
				contigs[rec.id].kmers[kmer_fwd] += 1
			elif kmer_rev in kmer_counts:
				contigs[rec.id].kmers[kmer_rev] += 1
			start += step
			stop += step

	print("\n## Normalizing counts")
	for contig in contigs.values():
		total = float(sum(contig.kmers.values()))
		for kmer, count in contig.kmers.items():
			if total > 0:
				contig.kmers[kmer] = 100*count/total
			else:
				contig.kmers[kmer] = 0.00

	print("\n## Performing PCA")
	df = pd.DataFrame(dict([(c.id, c.kmers) for c in contigs.values()]))
	pca = PCA(n_components=1)
	pca.fit(df)
	pc1 = pca.components_[0]

	print("\n## Computing per-contig deviation from the mean along the first principal component")
	mean_pc = np.mean(pc1)
	std_pc = np.std(pc1)
	for contig_id, contig_pc in zip(list(df.columns), pc1):
		contigs[contig_id].pc = contig_pc
		contigs[contig_id].values = {}
		contigs[contig_id].values['zscore'] = abs(contig_pc - mean_pc)/std_pc if std_pc > 0 else 0.0
		contigs[contig_id].values['delta'] = abs(contig_pc - mean_pc)
		contigs[contig_id].values['percent'] = 100*abs(contig_pc - mean_pc)/mean_pc

	print("\n## Identifying outlier contigs")
	flagged = []
	for contig in contigs.values():
		if contig.values['delta'] > args['cutoff']:
			flagged.append(contig.id)
	out = '%s/flagged_contigs' % args['tmp_dir']
	print ("   flagged contigs: %s" % out)
	with open(out, 'w') as f:
		for contig in flagged:
			f.write(contig+'\n')





