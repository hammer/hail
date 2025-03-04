import json
import os
import unittest

import shutil

import hail as hl
from ..helpers import *
from hail.utils import new_temp_file, FatalError, run_command, uri_path

setUpModule = startTestHailContext
tearDownModule = stopTestHailContext

_FLOAT_INFO_FIELDS = [
    'BaseQRankSum',
    'ClippingRankSum',
    'FS',
    'GQ_MEAN',
    'GQ_STDDEV',
    'HWP',
    'HaplotypeScore',
    'InbreedingCoeff',
    'MQ',
    'MQRankSum',
    'QD',
    'ReadPosRankSum',
    'VQSLOD',
]

_FLOAT_ARRAY_INFO_FIELDS = ['AF', 'MLEAF']


class VCFTests(unittest.TestCase):
    def test_info_char(self):
        self.assertEqual(hl.import_vcf(resource('infochar.vcf')).count_rows(), 1)

    def test_info_float64(self):
        """Test that floating-point info fields are 64-bit regardless of the entry float type"""
        mt = hl.import_vcf(resource('infochar.vcf'), entry_float_type=hl.tfloat32)
        for f in _FLOAT_INFO_FIELDS:
            self.assertEqual(mt['info'][f].dtype, hl.tfloat64)
        for f in _FLOAT_ARRAY_INFO_FIELDS:
            self.assertEqual(mt['info'][f].dtype, hl.tarray(hl.tfloat64))

    def test_glob(self):
        full = hl.import_vcf(resource('sample.vcf'))
        parts = hl.import_vcf(resource('samplepart*.vcf'))
        self.assertTrue(parts._same(full))

    def test_undeclared_info(self):
        mt = hl.import_vcf(resource('undeclaredinfo.vcf'))

        rows = mt.rows()
        self.assertTrue(rows.all(hl.is_defined(rows.info)))

        info_type = mt.row.dtype['info']
        self.assertTrue('InbreedingCoeff' in info_type)
        self.assertFalse('undeclared' in info_type)
        self.assertFalse('undeclaredFlag' in info_type)

    def test_malformed(self):
        with self.assertRaisesRegex(FatalError, "invalid character"):
            mt = hl.import_vcf(resource('malformed.vcf'))
            mt._force_count_rows()

    def test_not_identical_headers(self):
        t = new_temp_file('vcf')
        mt = hl.import_vcf(resource('sample.vcf'))
        hl.export_vcf(mt.filter_cols((mt.s != "C1048::HG02024") & (mt.s != "HG00255")), t)

        with self.assertRaisesRegex(FatalError, 'invalid sample IDs'):
            (hl.import_vcf([resource('sample.vcf'), t])
             ._force_count_rows())

    def test_filter(self):
        mt = hl.import_vcf(resource('malformed.vcf'), filter='rs685723')
        mt._force_count_rows()

        mt = hl.import_vcf(resource('sample.vcf'), filter=r'\trs\d+\t')
        assert mt.aggregate_rows(hl.agg.all(hl.is_missing(mt.rsid)))

    def test_find_replace(self):
        mt = hl.import_vcf(resource('sample.vcf'), find_replace=(r'\trs\d+\t', '\t.\t'))
        mt.rows().show()
        assert mt.aggregate_rows(hl.agg.all(hl.is_missing(mt.rsid)))

    def test_haploid(self):
        expected = hl.Table.parallelize(
            [hl.struct(locus = hl.locus("X", 16050036), s = "C1046::HG02024",
                       GT = hl.call(0, 0), AD = [10, 0], GQ = 44),
             hl.struct(locus = hl.locus("X", 16050036), s = "C1046::HG02025",
                       GT = hl.call(1), AD = [0, 6], GQ = 70),
             hl.struct(locus = hl.locus("X", 16061250), s = "C1046::HG02024",
                       GT = hl.call(2, 2), AD = [0, 0, 11], GQ = 33),
             hl.struct(locus = hl.locus("X", 16061250), s = "C1046::HG02025",
                       GT = hl.call(2), AD = [0, 0, 9], GQ = 24)],
            key=['locus', 's'])

        mt = hl.import_vcf(resource('haploid.vcf'))
        entries = mt.entries()
        entries = entries.key_by('locus', 's')
        entries = entries.select('GT', 'AD', 'GQ')
        self.assertTrue(entries._same(expected))

    def test_call_fields(self):
        expected = hl.Table.parallelize(
            [hl.struct(locus = hl.locus("X", 16050036), s = "C1046::HG02024",
                       GT = hl.call(0, 0), GTA = hl.null(hl.tcall), GTZ = hl.call(0, 1)),
             hl.struct(locus = hl.locus("X", 16050036), s = "C1046::HG02025",
                       GT = hl.call(1), GTA = hl.null(hl.tcall), GTZ = hl.call(0)),
             hl.struct(locus = hl.locus("X", 16061250), s = "C1046::HG02024",
                       GT = hl.call(2, 2), GTA = hl.call(2, 1), GTZ = hl.call(1, 1)),
             hl.struct(locus = hl.locus("X", 16061250), s = "C1046::HG02025",
                       GT = hl.call(2), GTA = hl.null(hl.tcall), GTZ = hl.call(1))],
            key=['locus', 's'])

        mt = hl.import_vcf(resource('generic.vcf'), call_fields=['GT', 'GTA', 'GTZ'])
        entries = mt.entries()
        entries = entries.key_by('locus', 's')
        entries = entries.select('GT', 'GTA', 'GTZ')
        self.assertTrue(entries._same(expected))

    def test_import_vcf(self):
        vcf = hl.split_multi_hts(
            hl.import_vcf(resource('sample2.vcf'),
                          reference_genome=hl.get_reference('GRCh38'),
                          contig_recoding={"22": "chr22"}))

        vcf_table = vcf.rows()
        self.assertTrue(vcf_table.all(vcf_table.locus.contig == "chr22"))
        self.assertTrue(vcf.locus.dtype, hl.tlocus('GRCh37'))

    def test_import_vcf_no_reference_specified(self):
        vcf = hl.import_vcf(resource('sample2.vcf'),
                            reference_genome=None)
        self.assertEqual(vcf.locus.dtype, hl.tstruct(contig=hl.tstr, position=hl.tint32))
        self.assertEqual(vcf.count_rows(), 735)

    def test_import_vcf_bad_reference_allele(self):
        vcf = hl.import_vcf(resource('invalid_base.vcf'))
        self.assertEqual(vcf.count_rows(), 1)

    def test_import_vcf_flags_are_defined(self):
        # issue 3277
        t = hl.import_vcf(resource('sample.vcf')).rows()
        self.assertTrue(t.all(hl.is_defined(t.info.NEGATIVE_TRAIN_SITE) &
                              hl.is_defined(t.info.POSITIVE_TRAIN_SITE) &
                              hl.is_defined(t.info.DB) &
                              hl.is_defined(t.info.DS)))

    def test_import_vcf_can_import_float_array_format(self):
        mt = hl.import_vcf(resource('floating_point_array.vcf'))
        self.assertTrue(mt.aggregate_entries(hl.agg.all(mt.numeric_array == [1.5, 2.5])))
        self.assertEqual(hl.tarray(hl.tfloat64), mt['numeric_array'].dtype)

    def test_import_vcf_can_import_float32_array_format(self):
        mt = hl.import_vcf(resource('floating_point_array.vcf'), entry_float_type=hl.tfloat32)
        self.assertTrue(mt.aggregate_entries(hl.agg.all(mt.numeric_array == [1.5, 2.5])))
        self.assertEqual(hl.tarray(hl.tfloat32), mt['numeric_array'].dtype)

    def test_import_vcf_can_import_negative_numbers(self):
        mt = hl.import_vcf(resource('negative_format_fields.vcf'))
        self.assertTrue(mt.aggregate_entries(hl.agg.all(mt.negative_int == -1) &
                                             hl.agg.all(mt.negative_float == -1.5) &
                                             hl.agg.all(mt.negative_int_array == [-1, -2]) &
                                             hl.agg.all(mt.negative_float_array == [-0.5, -1.5])))

    def test_import_vcf_missing_info_field_elements(self):
        mt = hl.import_vcf(resource('missingInfoArray.vcf'), reference_genome='GRCh37', array_elements_required=False)
        mt = mt.select_rows(FOO=mt.info.FOO, BAR=mt.info.BAR)
        expected = hl.Table.parallelize([{'locus': hl.Locus('X', 16050036), 'alleles': ['A', 'C'],
                                          'FOO': [1, None], 'BAR': [2, None, None]},
                                         {'locus': hl.Locus('X', 16061250), 'alleles': ['T', 'A', 'C'],
                                          'FOO': [None, 2, None], 'BAR': [None, 1.0, None]}],
                                        hl.tstruct(locus=hl.tlocus('GRCh37'), alleles=hl.tarray(hl.tstr),
                                                   FOO=hl.tarray(hl.tint), BAR=hl.tarray(hl.tfloat64)),
                                        key=['locus', 'alleles'])
        self.assertTrue(mt.rows()._same(expected))

    def test_import_vcf_missing_format_field_elements(self):
        mt = hl.import_vcf(resource('missingFormatArray.vcf'), reference_genome='GRCh37', array_elements_required=False)
        mt = mt.select_rows().select_entries('AD', 'PL')

        expected = hl.Table.parallelize([{'locus': hl.Locus('X', 16050036), 'alleles': ['A', 'C'], 's': 'C1046::HG02024',
                                          'AD': [None, None], 'PL': [0, None, 180]},
                                         {'locus': hl.Locus('X', 16050036), 'alleles': ['A', 'C'], 's': 'C1046::HG02025',
                                          'AD': [None, 6], 'PL': [70, None]},
                                         {'locus': hl.Locus('X', 16061250), 'alleles': ['T', 'A', 'C'], 's': 'C1046::HG02024',
                                          'AD': [0, 0, None], 'PL': [396, None, None, 33, None, 0]},
                                         {'locus': hl.Locus('X', 16061250), 'alleles': ['T', 'A', 'C'], 's': 'C1046::HG02025',
                                          'AD': [0, 0, 9], 'PL': [None, None, None]}],
                                        hl.tstruct(locus=hl.tlocus('GRCh37'), alleles=hl.tarray(hl.tstr), s=hl.tstr,
                                                   AD=hl.tarray(hl.tint), PL=hl.tarray(hl.tint)),
                                        key=['locus', 'alleles', 's'])

        self.assertTrue(mt.entries()._same(expected))

    def test_import_vcf_skip_invalid_loci(self):
        mt = hl.import_vcf(resource('skip_invalid_loci.vcf'), reference_genome='GRCh37',
                           skip_invalid_loci=True)
        self.assertEqual(mt._force_count_rows(), 3)

        with self.assertRaisesRegex(FatalError, 'Invalid locus'):
            hl.import_vcf(resource('skip_invalid_loci.vcf')).count()

    def test_import_vcf_set_field_missing(self):
        mt = hl.import_vcf(resource('test_set_field_missing.vcf'))
        mt.aggregate_entries(hl.agg.sum(mt.DP))

    def test_import_vcf_dosages_as_doubles_or_floats(self):
        mt = hl.import_vcf(resource('small-ds.vcf'))
        self.assertEqual(hl.expr.expressions.typed_expressions.Float64Expression, type(mt.entry.DS))
        mt32 = hl.import_vcf(resource('small-ds.vcf'),  entry_float_type=hl.tfloat32)
        self.assertEqual(hl.expr.expressions.typed_expressions.Float32Expression, type(mt32.entry.DS))
        mt_result = mt.annotate_entries(DS32=mt32.index_entries(mt.row_key, mt.col_key).DS)
        compare = mt_result.annotate_entries(
            test=(hl.coalesce(hl.approx_equal(mt_result.DS, mt_result.DS32, nan_same=True), True))
        )
        self.assertTrue(all(compare.test.collect()))

    def test_import_vcf_invalid_float_type(self):
        with self.assertRaises(TypeError):
            mt = hl.import_vcf(resource('small-ds.vcf'), entry_float_type=hl.tstr)
        with self.assertRaises(TypeError):
            mt = hl.import_vcf(resource('small-ds.vcf'), entry_float_type=hl.tint)
        with self.assertRaises(TypeError):
            mt = hl.import_vcf(resource('small-ds.vcf'), entry_float_type=hl.tint32)
        with self.assertRaises(TypeError):
            mt = hl.import_vcf(resource('small-ds.vcf'), entry_float_type=hl.tint64)

    def test_export_vcf(self):
        dataset = hl.import_vcf(resource('sample.vcf.bgz'))
        vcf_metadata = hl.get_vcf_metadata(resource('sample.vcf.bgz'))
        hl.export_vcf(dataset, '/tmp/sample.vcf', metadata=vcf_metadata)
        dataset_imported = hl.import_vcf('/tmp/sample.vcf')
        self.assertTrue(dataset._same(dataset_imported))

        no_sample_dataset = dataset.filter_cols(False).select_entries()
        hl.export_vcf(no_sample_dataset, '/tmp/no_sample.vcf', metadata=vcf_metadata)
        no_sample_dataset_imported = hl.import_vcf('/tmp/no_sample.vcf')
        self.assertTrue(no_sample_dataset._same(no_sample_dataset_imported))

        metadata_imported = hl.get_vcf_metadata('/tmp/sample.vcf')
        # are py4 JavaMaps, not dicts, so can't use assertDictEqual
        self.assertEqual(vcf_metadata, metadata_imported)

    def test_export_vcf_empty_format(self):
        mt = hl.import_vcf(resource('sample.vcf.bgz')).select_entries()
        tmp = new_temp_file(suffix="vcf")
        hl.export_vcf(mt, tmp)

        assert hl.import_vcf(tmp)._same(mt)

    def test_export_vcf_no_gt(self):
        mt = hl.import_vcf(resource('sample.vcf.bgz')).drop('GT')
        tmp = new_temp_file(suffix="vcf")
        hl.export_vcf(mt, tmp)

        assert hl.import_vcf(tmp)._same(mt)

    def test_export_vcf_no_alt_alleles(self):
        mt = hl.import_vcf(resource('gvcfs/HG0096_excerpt.g.vcf'), reference_genome='GRCh38')
        self.assertEqual(mt.filter_rows(hl.len(mt.alleles) == 1).count_rows(), 5)

        tmp = new_temp_file(suffix="vcf")
        hl.export_vcf(mt, tmp)
        mt2 = hl.import_vcf(tmp, reference_genome='GRCh38')
        self.assertTrue(mt._same(mt2))

    @skip_unless_spark_backend()
    def test_import_vcfs(self):
        path = resource('sample.vcf.bgz')
        parts = [
            hl.Interval(start=hl.Struct(locus=hl.Locus('20', 1)),
                        end=hl.Struct(locus=hl.Locus('20', 13509135)),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('20', 13509136)),
                        end=hl.Struct(locus=hl.Locus('20', 16493533)),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('20', 16493534)),
                        end=hl.Struct(locus=hl.Locus('20', 20000000)),
                        includes_end=True)
        ]
        vcf1 = hl.import_vcf(path).key_rows_by('locus')
        vcf2 = hl.import_vcfs([path], parts)[0]
        self.assertEqual(len(parts), vcf2.n_partitions())
        self.assertTrue(vcf1._same(vcf2))

        interval = [hl.parse_locus_interval('[20:13509136-16493533]')]
        filter1 = hl.filter_intervals(vcf1, interval)
        filter2 = hl.filter_intervals(vcf2, interval)
        self.assertEqual(1, filter2.n_partitions())
        self.assertTrue(filter1._same(filter2))

        # we've selected exactly the middle partition ±1 position on either end
        interval_a = [hl.parse_locus_interval('[20:13509135-16493533]')]
        interval_b = [hl.parse_locus_interval('[20:13509136-16493534]')]
        interval_c = [hl.parse_locus_interval('[20:13509135-16493534]')]
        self.assertEqual(hl.filter_intervals(vcf2, interval_a).n_partitions(), 2)
        self.assertEqual(hl.filter_intervals(vcf2, interval_b).n_partitions(), 2)
        self.assertEqual(hl.filter_intervals(vcf2, interval_c).n_partitions(), 3)

    @skip_unless_spark_backend()
    def test_import_vcfs_subset(self):
        path = resource('sample.vcf.bgz')
        parts = [
            hl.Interval(start=hl.Struct(locus=hl.Locus('20', 13509136)),
                        end=hl.Struct(locus=hl.Locus('20', 16493533)),
                        includes_end=True)
        ]
        vcf1 = hl.import_vcf(path).key_rows_by('locus')
        vcf2 = hl.import_vcfs([path], parts)[0]
        interval = [hl.parse_locus_interval('[20:13509136-16493533]')]
        filter1 = hl.filter_intervals(vcf1, interval)
        self.assertTrue(vcf2._same(filter1))
        self.assertEqual(len(parts), vcf2.n_partitions())

    def test_vcf_parser_golden_master(self):
        files = [(resource('ex.vcf'), 'GRCh37'),
                 (resource('sample.vcf'), 'GRCh37'),
                 (resource('gvcfs/HG00096.g.vcf.gz'), 'GRCh38')]
        for vcf_path, rg in files:
            vcf = hl.import_vcf(
                vcf_path,
                reference_genome=rg,
                array_elements_required=False,
                force_bgz=True)
            mt = hl.read_matrix_table(vcf_path + '.mt')
            self.assertTrue(mt._same(vcf))


    @skip_unless_spark_backend()
    def test_import_multiple_vcfs(self):
        _paths = ['gvcfs/HG00096.g.vcf.gz', 'gvcfs/HG00268.g.vcf.gz']
        paths = [resource(p) for p in _paths]
        parts = [
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 17821257, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 18708366, reference_genome='GRCh38')),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 18708367, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 19776611, reference_genome='GRCh38')),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 19776612, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 21144633, reference_genome='GRCh38')),
                        includes_end=True)
        ]
        int0 = hl.parse_locus_interval('[chr20:17821257-18708366]', reference_genome='GRCh38')
        int1 = hl.parse_locus_interval('[chr20:18708367-19776611]', reference_genome='GRCh38')
        hg00096, hg00268 = hl.import_vcfs(paths, parts, reference_genome='GRCh38')
        filt096 = hl.filter_intervals(hg00096, [int0])
        filt268 = hl.filter_intervals(hg00268, [int1])
        self.assertEqual(1, filt096.n_partitions())
        self.assertEqual(1, filt268.n_partitions())
        pos096 = set(filt096.locus.position.collect())
        pos268 = set(filt268.locus.position.collect())
        self.assertFalse(pos096 & pos268)

    @skip_unless_spark_backend()
    def test_combiner_works(self):
        from hail.experimental.vcf_combiner import transform_one, combine_gvcfs
        _paths = ['gvcfs/HG00096.g.vcf.gz', 'gvcfs/HG00268.g.vcf.gz']
        paths = [resource(p) for p in _paths]
        parts = [
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 17821257, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 18708366, reference_genome='GRCh38')),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 18708367, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 19776611, reference_genome='GRCh38')),
                        includes_end=True),
            hl.Interval(start=hl.Struct(locus=hl.Locus('chr20', 19776612, reference_genome='GRCh38')),
                        end=hl.Struct(locus=hl.Locus('chr20', 21144633, reference_genome='GRCh38')),
                        includes_end=True)
        ]
        vcfs = [transform_one(mt.annotate_rows(info=mt.info.annotate(
            MQ_DP=hl.null(hl.tint32),
            VarDP=hl.null(hl.tint32),
            QUALapprox=hl.null(hl.tint32))))
                for mt in hl.import_vcfs(paths, parts, reference_genome='GRCh38',
                                         array_elements_required=False)]
        comb = combine_gvcfs(vcfs)
        self.assertEqual(len(parts), comb.n_partitions())
        comb._force_count_rows()


class PLINKTests(unittest.TestCase):
    def test_import_fam(self):
        fam_file = resource('sample.fam')
        nfam = hl.import_fam(fam_file).count()
        i = 0
        with open(fam_file) as f:
            for line in f:
                if len(line.strip()) != 0:
                    i += 1
        self.assertEqual(nfam, i)

    def test_export_import_plink_same(self):
        mt = get_dataset()
        mt = mt.select_rows(rsid=hl.delimit([mt.locus.contig, hl.str(mt.locus.position), mt.alleles[0], mt.alleles[1]], ':'),
                            cm_position=15.0)
        mt = mt.select_cols(fam_id=hl.null(hl.tstr), pat_id=hl.null(hl.tstr), mat_id=hl.null(hl.tstr),
                            is_female=hl.null(hl.tbool), is_case=hl.null(hl.tbool))
        mt = mt.select_entries('GT')

        bfile = '/tmp/test_import_export_plink'
        hl.export_plink(mt, bfile, ind_id=mt.s, cm_position=mt.cm_position)

        mt_imported = hl.import_plink(bfile + '.bed', bfile + '.bim', bfile + '.fam',
                                      a2_reference=True, reference_genome='GRCh37')
        self.assertTrue(mt._same(mt_imported))
        self.assertTrue(mt.aggregate_rows(hl.agg.all(mt.cm_position == 15.0)))

    def test_import_plink_empty_fam(self):
        mt = get_dataset().filter_cols(False)
        bfile = '/tmp/test_empty_fam'
        hl.export_plink(mt, bfile, ind_id=mt.s)
        with self.assertRaisesRegex(FatalError, "Empty FAM file"):
            hl.import_plink(bfile + '.bed', bfile + '.bim', bfile + '.fam')

    def test_import_plink_empty_bim(self):
        mt = get_dataset().filter_rows(False)
        bfile = '/tmp/test_empty_bim'
        hl.export_plink(mt, bfile, ind_id=mt.s)
        with self.assertRaisesRegex(FatalError, "BIM file does not contain any variants"):
            hl.import_plink(bfile + '.bed', bfile + '.bim', bfile + '.fam')

    def test_import_plink_a1_major(self):
        mt = get_dataset()
        bfile = '/tmp/sample_plink'
        hl.export_plink(mt, bfile, ind_id=mt.s)

        def get_data(a2_reference):
            mt_imported = hl.import_plink(bfile + '.bed', bfile + '.bim',
                                          bfile + '.fam', a2_reference=a2_reference)
            return (hl.variant_qc(mt_imported)
                    .rows()
                    .key_by('rsid'))

        a2 = get_data(a2_reference=True)
        a1 = get_data(a2_reference=False)

        j = (a2.annotate(a1_alleles=a1[a2.rsid].alleles, a1_vqc=a1[a2.rsid].variant_qc)
             .rename({'variant_qc': 'a2_vqc', 'alleles': 'a2_alleles'}))

        self.assertTrue(j.all((j.a1_alleles[0] == j.a2_alleles[1]) &
                              (j.a1_alleles[1] == j.a2_alleles[0]) &
                              (j.a1_vqc.n_not_called == j.a2_vqc.n_not_called) &
                              (j.a1_vqc.n_het == j.a2_vqc.n_het) &
                              (j.a1_vqc.homozygote_count[0] == j.a2_vqc.homozygote_count[1]) &
                              (j.a1_vqc.homozygote_count[1] == j.a2_vqc.homozygote_count[0])))

    def test_import_plink_contig_recoding_w_reference(self):
        vcf = hl.split_multi_hts(
            hl.import_vcf(resource('sample2.vcf'),
                          reference_genome=hl.get_reference('GRCh38'),
                          contig_recoding={"22": "chr22"}))

        hl.export_plink(vcf, '/tmp/sample_plink')

        bfile = '/tmp/sample_plink'
        plink = hl.import_plink(
            bfile + '.bed', bfile + '.bim', bfile + '.fam',
            a2_reference=True,
            contig_recoding={'chr22': '22'},
            reference_genome='GRCh37').rows()
        self.assertTrue(plink.all(plink.locus.contig == "22"))
        self.assertEqual(vcf.count_rows(), plink.count())
        self.assertTrue(plink.locus.dtype, hl.tlocus('GRCh37'))

    def test_import_plink_no_reference_specified(self):
        bfile = resource('fastlmmTest')
        plink = hl.import_plink(bfile + '.bed', bfile + '.bim', bfile + '.fam',
                                reference_genome=None)
        self.assertEqual(plink.locus.dtype,
                         hl.tstruct(contig=hl.tstr, position=hl.tint32))

    def test_import_plink_skip_invalid_loci(self):
        mt = hl.import_plink(resource('skip_invalid_loci.bed'),
                             resource('skip_invalid_loci.bim'),
                             resource('skip_invalid_loci.fam'),
                             reference_genome='GRCh37',
                             skip_invalid_loci=True)
        self.assertEqual(mt._force_count_rows(), 3)

        with self.assertRaisesRegex(FatalError, 'Invalid locus'):
            (hl.import_plink(resource('skip_invalid_loci.bed'),
                            resource('skip_invalid_loci.bim'),
                            resource('skip_invalid_loci.fam'))
             ._force_count_rows())

    @unittest.skipIf('HAIL_TEST_SKIP_PLINK' in os.environ, 'Skipping tests requiring plink')
    def test_export_plink(self):
        vcf_file = resource('sample.vcf')
        mt = hl.split_multi_hts(hl.import_vcf(vcf_file, min_partitions=10))

        # permute columns so not in alphabetical order!
        import random
        indices = list(range(mt.count_cols()))
        random.shuffle(indices)
        mt = mt.choose_cols(indices)

        split_vcf_file = uri_path(new_temp_file())
        hl_output = uri_path(new_temp_file())
        plink_output = uri_path(new_temp_file())
        merge_output = uri_path(new_temp_file())

        hl.export_vcf(mt, split_vcf_file)
        hl.export_plink(mt, hl_output)

        run_command(["plink", "--vcf", split_vcf_file,
                     "--make-bed", "--out", plink_output,
                     "--const-fid", "--keep-allele-order"])

        data = []
        with open(uri_path(plink_output + ".bim")) as file:
            for line in file:
                row = line.strip().split()
                row[1] = ":".join([row[0], row[3], row[5], row[4]])
                data.append("\t".join(row) + "\n")

        with open(plink_output + ".bim", 'w') as f:
            f.writelines(data)

        run_command(["plink", "--bfile", plink_output,
                     "--bmerge", hl_output, "--merge-mode",
                     "6", "--out", merge_output])

        same = True
        with open(merge_output + ".diff") as f:
            for line in f:
                row = line.strip().split()
                if row != ["SNP", "FID", "IID", "NEW", "OLD"]:
                    same = False
                    break

        self.assertTrue(same)

    def test_export_plink_exprs(self):
        ds = get_dataset()
        fam_mapping = {'f0': 'fam_id', 'f1': 'ind_id', 'f2': 'pat_id', 'f3': 'mat_id',
                       'f4': 'is_female', 'f5': 'pheno'}
        bim_mapping = {'f0': 'contig', 'f1': 'varid', 'f2': 'cm_position',
                       'f3': 'position', 'f4': 'a1', 'f5': 'a2'}

        # Test default arguments
        out1 = new_temp_file()
        hl.export_plink(ds, out1)
        fam1 = (hl.import_table(out1 + '.fam', no_header=True, impute=False, missing="")
                .rename(fam_mapping))
        bim1 = (hl.import_table(out1 + '.bim', no_header=True, impute=False)
                .rename(bim_mapping))

        self.assertTrue(fam1.all((fam1.fam_id == "0") & (fam1.pat_id == "0") &
                                 (fam1.mat_id == "0") & (fam1.is_female == "0") &
                                 (fam1.pheno == "NA")))
        self.assertTrue(bim1.all((bim1.varid == bim1.contig + ":" + bim1.position + ":" + bim1.a2 + ":" + bim1.a1) &
                                 (bim1.cm_position == "0.0")))

        # Test non-default FAM arguments
        out2 = new_temp_file()
        hl.export_plink(ds, out2, ind_id=ds.s, fam_id=ds.s, pat_id="nope",
                        mat_id="nada", is_female=True, pheno=False)
        fam2 = (hl.import_table(out2 + '.fam', no_header=True, impute=False, missing="")
                .rename(fam_mapping))

        self.assertTrue(fam2.all((fam2.fam_id == fam2.ind_id) & (fam2.pat_id == "nope") &
                                 (fam2.mat_id == "nada") & (fam2.is_female == "2") &
                                 (fam2.pheno == "1")))

        # Test quantitative phenotype
        out3 = new_temp_file()
        hl.export_plink(ds, out3, ind_id=ds.s, pheno=hl.float64(hl.len(ds.s)))
        fam3 = (hl.import_table(out3 + '.fam', no_header=True, impute=False, missing="")
                .rename(fam_mapping))

        self.assertTrue(fam3.all((fam3.fam_id == "0") & (fam3.pat_id == "0") &
                                 (fam3.mat_id == "0") & (fam3.is_female == "0") &
                                 (fam3.pheno != "0") & (fam3.pheno != "NA")))

        # Test non-default BIM arguments
        out4 = new_temp_file()
        hl.export_plink(ds, out4, varid="hello", cm_position=100)
        bim4 = (hl.import_table(out4 + '.bim', no_header=True, impute=False)
                .rename(bim_mapping))

        self.assertTrue(bim4.all((bim4.varid == "hello") & (bim4.cm_position == "100.0")))

        # Test call expr
        out5 = new_temp_file()
        ds_call = ds.annotate_entries(gt_fake=hl.call(0, 0))
        hl.export_plink(ds_call, out5, call=ds_call.gt_fake)
        ds_all_hom_ref = hl.import_plink(out5 + '.bed', out5 + '.bim', out5 + '.fam')
        nerrors = ds_all_hom_ref.aggregate_entries(hl.agg.count_where(~ds_all_hom_ref.GT.is_hom_ref()))
        self.assertTrue(nerrors == 0)

        # Test white-space in FAM id expr raises error
        with self.assertRaisesRegex(TypeError, "has spaces in the following values:"):
            hl.export_plink(ds, new_temp_file(), mat_id="hello world")

        # Test white-space in varid expr raises error
        with self.assertRaisesRegex(FatalError, "no white space allowed:"):
            hl.export_plink(ds, new_temp_file(), varid="hello world")

    def test_contig_recoding_defaults(self):
        hl.import_plink(resource('sex_mt_contigs.bed'),
                        resource('sex_mt_contigs.bim'),
                        resource('sex_mt_contigs.fam'),
                        reference_genome='GRCh37')

        hl.import_plink(resource('sex_mt_contigs.bed'),
                        resource('sex_mt_contigs.bim'),
                        resource('sex_mt_contigs.fam'),
                        reference_genome='GRCh38')

        rg_random = hl.ReferenceGenome("random", ['1', '23', '24', '25', '26'],
                                       {'1': 10, '23': 10, '24': 10, '25': 10, '26': 10})

        hl.import_plink(resource('sex_mt_contigs.bed'),
                        resource('sex_mt_contigs.bim'),
                        resource('sex_mt_contigs.fam'),
                        reference_genome='random')


# this routine was used to generate resources random.gen, random.sample
# random.bgen was generated with qctool v2.0rc9:
# qctool -g random.gen -s random.sample -bgen-bits 8 -og random.bgen
#
# random-a.bgen, random-b.bgen, random-c.bgen was generated as follows:
# head -n 10 random.gen > random-a.gen; head -n 20 random.gen | tail -n 10 > random-b.gen; tail -n 10 random.gen > random-c.gen
# qctool -g random-a.gen -s random.sample -og random-a.bgen -bgen-bits 8
# qctool -g random-b.gen -s random.sample -og random-b.bgen -bgen-bits 8
# qctool -g random-c.gen -s random.sample -og random-c.bgen -bgen-bits 8
#
# random-*-disjoint.bgen was generated as follows:
# while read line; do echo $RANDOM $line; done < src/test/resources/random.gen | sort -n | cut -f2- -d' ' > random-shuffled.gen
# head -n 10 random-shuffled.gen > random-a-disjoint.gen; head -n 20 random-shuffled.gen | tail -n 10 > random-b-disjoint.gen; tail -n 10 random-shuffled.gen > random-c-disjoint.gen
# qctool -g random-a-disjoint.gen -s random.sample -og random-a-disjoint.bgen -bgen-bits 8
# qctool -g random-b-disjoint.gen -s random.sample -og random-b-disjoint.bgen -bgen-bits 8
# qctool -g random-c-disjoint.gen -s random.sample -og random-c-disjoint.bgen -bgen-bits 8
def generate_random_gen():
    mt = hl.utils.range_matrix_table(30, 10)
    mt = (mt.annotate_rows(locus = hl.locus('20', mt.row_idx + 1),
                           alleles = ['A', 'G'])
          .key_rows_by('locus', 'alleles'))
    mt = (mt.annotate_cols(s = hl.str(mt.col_idx))
          .key_cols_by('s'))
    # using totally random values leads rounding differences where
    # identical GEN values get rounded differently, leading to
    # differences in the GT call between import_{gen, bgen}
    mt = mt.annotate_entries(a = hl.int32(hl.rand_unif(0.0, 255.0)))
    mt = mt.annotate_entries(b = hl.int32(hl.rand_unif(0.0, 255.0 - mt.a)))
    mt = mt.transmute_entries(GP = hl.array([mt.a, mt.b, 255.0 - mt.a - mt.b]) / 255.0)
    # 20% missing
    mt = mt.filter_entries(hl.rand_bool(0.8))
    hl.export_gen(mt, 'random', precision=4)


class BGENTests(unittest.TestCase):
    def test_import_bgen_dosage_entry(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['dosage'])
        self.assertEqual(bgen.entry.dtype, hl.tstruct(dosage=hl.tfloat64))
        self.assertEqual(bgen.count_rows(), 199)

    def test_import_bgen_GT_GP_entries(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['GT', 'GP'],
                              sample_file=resource('example.sample'))
        self.assertEqual(bgen.entry.dtype, hl.tstruct(GT=hl.tcall, GP=hl.tarray(hl.tfloat64)))

    def test_import_bgen_no_entries(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=[],
                              sample_file=resource('example.sample'))
        self.assertEqual(bgen.entry.dtype, hl.tstruct())

    def test_import_bgen_no_reference(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome=None)

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['GT', 'GP', 'dosage'])
        self.assertEqual(bgen.locus.dtype, hl.tstruct(contig=hl.tstr, position=hl.tint32))
        self.assertEqual(bgen.count_rows(), 199)

    def test_import_bgen_skip_invalid_loci(self):
        # Note: the skip_invalid_loci.bgen has 16-bit probabilities, and Hail
        # will crash if the genotypes are decoded
        hl.index_bgen(resource('skip_invalid_loci.bgen'),
                      reference_genome='GRCh37',
                      skip_invalid_loci=True)

        mt = hl.import_bgen(resource('skip_invalid_loci.bgen'),
                            entry_fields=[],
                            sample_file=resource('skip_invalid_loci.sample'))
        self.assertEqual(mt.rows().count(), 3)

        with self.assertRaisesRegex(FatalError, 'Invalid locus'):
            hl.index_bgen(resource('skip_invalid_loci.bgen'))

            mt = hl.import_bgen(resource('skip_invalid_loci.bgen'),
                                entry_fields=[],
                                sample_file=resource('skip_invalid_loci.sample'))
            mt.rows().count()

    def test_import_bgen_gavin_example(self):
        recoding = {'0{}'.format(i): str(i) for i in range(1, 10)}

        sample_file = resource('example.sample')
        genmt = hl.import_gen(resource('example.gen'), sample_file,
                              contig_recoding=recoding,
                              reference_genome="GRCh37")

        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file, contig_recoding=recoding,
                      reference_genome="GRCh37")
        bgenmt = hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file)
        self.assertTrue(
            bgenmt._same(genmt, tolerance=1.0 / 255, absolute=True))

    def test_import_bgen_random(self):
        sample_file = resource('random.sample')
        genmt = hl.import_gen(resource('random.gen'), sample_file)

        bgen_file = resource('random.bgen')
        hl.index_bgen(bgen_file)
        bgenmt = hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file)
        self.assertTrue(
            bgenmt._same(genmt, tolerance=1.0 / 255, absolute=True))

    def test_parallel_import(self):
        bgen_file = resource('parallelBgenExport.bgen')
        hl.index_bgen(bgen_file)
        mt = hl.import_bgen(bgen_file,
                            ['GT', 'GP'],
                            resource('parallelBgenExport.sample'))
        self.assertEqual(mt.count(), (16, 10))

    def test_import_bgen_dosage_and_gp_dosage_function_agree(self):
        recoding = {'0{}'.format(i): str(i) for i in range(1, 10)}

        sample_file = resource('example.sample')
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file,
                      contig_recoding=recoding)

        bgenmt = hl.import_bgen(bgen_file, ['GP', 'dosage'], sample_file)
        et = bgenmt.entries()
        et = et.transmute(gp_dosage = hl.gp_dosage(et.GP))
        self.assertTrue(et.all(
            (hl.is_missing(et.dosage) & hl.is_missing(et.gp_dosage)) |
            (hl.abs(et.dosage - et.gp_dosage) < 1e-6)))

    def test_import_bgen_row_fields(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        default_row_fields = hl.import_bgen(resource('example.8bits.bgen'),
                                            entry_fields=['dosage'])
        self.assertEqual(default_row_fields.row.dtype,
                         hl.tstruct(locus=hl.tlocus('GRCh37'),
                                    alleles=hl.tarray(hl.tstr),
                                    rsid=hl.tstr,
                                    varid=hl.tstr))
        no_row_fields = hl.import_bgen(resource('example.8bits.bgen'),
                                       entry_fields=['dosage'],
                                       _row_fields=[])
        self.assertEqual(no_row_fields.row.dtype,
                         hl.tstruct(locus=hl.tlocus('GRCh37'),
                                    alleles=hl.tarray(hl.tstr)))
        varid_only = hl.import_bgen(resource('example.8bits.bgen'),
                                    entry_fields=['dosage'],
                                    _row_fields=['varid'])
        self.assertEqual(varid_only.row.dtype,
                         hl.tstruct(locus=hl.tlocus('GRCh37'),
                                    alleles=hl.tarray(hl.tstr),
                                    varid=hl.tstr))
        rsid_only = hl.import_bgen(resource('example.8bits.bgen'),
                                   entry_fields=['dosage'],
                                   _row_fields=['rsid'])
        self.assertEqual(rsid_only.row.dtype,
                         hl.tstruct(locus=hl.tlocus('GRCh37'),
                                    alleles=hl.tarray(hl.tstr),
                                    rsid=hl.tstr))

        self.assertTrue(default_row_fields.drop('varid')._same(rsid_only))
        self.assertTrue(default_row_fields.drop('rsid')._same(varid_only))
        self.assertTrue(
            default_row_fields.drop('varid', 'rsid')._same(no_row_fields))

    def test_import_bgen_variant_filtering_from_literals(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file,
                      contig_recoding={'01': '1'})

        alleles = ['A', 'G']

        desired_variants = [
            hl.Struct(locus=hl.Locus('1', 2000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 2001), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 4000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 10000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 100001), alleles=alleles),
        ]

        expected_result = [
            hl.Struct(locus=hl.Locus('1', 2000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 2001), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 4000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 10000), alleles=alleles),
            hl.Struct(locus=hl.Locus('1', 10000), alleles=alleles), # Duplicated variant
            hl.Struct(locus=hl.Locus('1', 100001), alleles=alleles),
        ]

        part_1 = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=1, # forcing seek to be called
                                variants=desired_variants)
        self.assertEqual(part_1.rows().key_by('locus', 'alleles').select().collect(), expected_result)

        part_199 = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=199, # forcing each variant to be its own partition for testing duplicates work properly
                                variants=desired_variants)
        self.assertEqual(part_199.rows().key_by('locus', 'alleles').select().collect(), expected_result)

        everything = hl.import_bgen(bgen_file, ['GT'])
        self.assertEqual(everything.count(), (199, 500))

        expected = everything.filter_rows(hl.set(desired_variants).contains(everything.row_key))

        self.assertTrue(expected._same(part_1))

    def test_import_bgen_locus_filtering_from_literals(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file,
                      contig_recoding={'01': '1'})

        # Test with Struct(Locus)
        desired_loci = [hl.Struct(locus=hl.Locus('1', 10000))]

        expected_result = [
            hl.Struct(locus=hl.Locus('1', 10000), alleles=['A', 'G']),
            hl.Struct(locus=hl.Locus('1', 10000), alleles=['A', 'G']) # Duplicated variant
        ]

        locus_struct = hl.import_bgen(bgen_file,
                                      ['GT'],
                                      variants=desired_loci)
        self.assertEqual(locus_struct.rows().key_by('locus', 'alleles').select().collect(),
                         expected_result)

        # Test with Locus object
        desired_loci = [hl.Locus('1', 10000)]

        locus_object = hl.import_bgen(bgen_file,
                                      ['GT'],
                                      variants=desired_loci)
        self.assertEqual(locus_object.rows().key_by('locus', 'alleles').select().collect(),
                         expected_result)

    def test_import_bgen_variant_filtering_from_exprs(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file, contig_recoding={'01': '1'})

        everything = hl.import_bgen(bgen_file, ['GT'])
        self.assertEqual(everything.count(), (199, 500))

        desired_variants = hl.struct(locus=everything.locus, alleles=everything.alleles)

        actual = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=10,
                                variants=desired_variants) # filtering with everything

        self.assertTrue(everything._same(actual))

    def test_import_bgen_locus_filtering_from_exprs(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file, contig_recoding={'01': '1'})

        everything = hl.import_bgen(bgen_file, ['GT'])
        self.assertEqual(everything.count(), (199, 500))

        actual_struct = hl.import_bgen(bgen_file,
                                ['GT'],
                                variants=hl.struct(locus=everything.locus))

        self.assertTrue(everything._same(actual_struct))

        actual_locus = hl.import_bgen(bgen_file,
                                ['GT'],
                                variants=everything.locus)

        self.assertTrue(everything._same(actual_locus))

    def test_import_bgen_variant_filtering_from_table(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file, contig_recoding={'01': '1'})

        everything = hl.import_bgen(bgen_file, ['GT'])
        self.assertEqual(everything.count(), (199, 500))

        desired_variants = everything.rows()

        actual = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=10,
                                variants=desired_variants) # filtering with everything

        self.assertTrue(everything._same(actual))

    def test_import_bgen_locus_filtering_from_table(self):
        bgen_file = resource('example.8bits.bgen')
        hl.index_bgen(bgen_file, contig_recoding={'01': '1'})

        desired_loci = hl.Table.parallelize([{'locus': hl.Locus('1', 10000)}],
                                            schema=hl.tstruct(locus=hl.tlocus()),
                                            key='locus')

        expected_result = [
            hl.Struct(locus=hl.Locus('1', 10000), alleles=['A', 'G']),
            hl.Struct(locus=hl.Locus('1', 10000), alleles=['A', 'G'])  # Duplicated variant
        ]

        result = hl.import_bgen(bgen_file,
                                ['GT'],
                                variants=desired_loci)

        self.assertEqual(result.rows().key_by('locus', 'alleles').select().collect(),
                        expected_result)

    def test_import_bgen_empty_variant_filter(self):
        bgen_file = resource('example.8bits.bgen')

        hl.index_bgen(bgen_file,
                      contig_recoding={'01': '1'})

        actual = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=10,
                                variants=[])
        self.assertEqual(actual.count_rows(), 0)

        nothing = hl.import_bgen(bgen_file, ['GT']).filter_rows(False)
        self.assertEqual(nothing.count(), (0, 500))

        desired_variants = hl.struct(locus=nothing.locus, alleles=nothing.alleles)

        actual = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=10,
                                variants=desired_variants)
        self.assertEqual(actual.count_rows(), 0)

    # FIXME testing block_size (in MB) requires large BGEN
    def test_n_partitions(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['dosage'],
                              n_partitions=210)
        self.assertEqual(bgen.n_partitions(), 199) # only 199 variants in the file

    def test_drop(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      contig_recoding={'01': '1'},
                      reference_genome='GRCh37')

        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['dosage'])

        dr = bgen.filter_rows(False)
        self.assertEqual(dr._force_count_rows(), 0)
        self.assertEqual(dr._force_count_cols(), 500)

        dc = bgen.filter_cols(False)
        self.assertEqual(dc._force_count_rows(), 199)
        self.assertEqual(dc._force_count_cols(), 0)

    def test_multiple_files(self):
        sample_file = resource('random.sample')
        genmt = hl.import_gen(resource('random.gen'), sample_file)

        bgen_file = [resource('random-b.bgen'), resource('random-c.bgen'), resource('random-a.bgen')]
        hl.index_bgen(bgen_file)
        bgenmt = hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file, n_partitions=3)
        self.assertTrue(
            bgenmt._same(genmt, tolerance=1.0 / 255, absolute=True))

    def test_multiple_files_variant_filtering(self):
        bgen_file = [resource('random-b.bgen'), resource('random-c.bgen'), resource('random-a.bgen')]
        hl.index_bgen(bgen_file)

        alleles = ['A', 'G']

        desired_variants = [
            hl.Struct(locus=hl.Locus('20', 11), alleles=alleles),
            hl.Struct(locus=hl.Locus('20', 13), alleles=alleles),
            hl.Struct(locus=hl.Locus('20', 29), alleles=alleles),
            hl.Struct(locus=hl.Locus('20', 28), alleles=alleles),
            hl.Struct(locus=hl.Locus('20', 1), alleles=alleles),
            hl.Struct(locus=hl.Locus('20', 12), alleles=alleles),
        ]

        actual = hl.import_bgen(bgen_file,
                                ['GT'],
                                n_partitions=10,
                                variants=desired_variants)
        self.assertEqual(actual.count_rows(), 6)

        everything = hl.import_bgen(bgen_file,
                                    ['GT'])
        self.assertEqual(everything.count(), (30, 10))

        expected = everything.filter_rows(hl.set(desired_variants).contains(everything.row_key))

        self.assertTrue(expected._same(actual))

    def test_multiple_files_disjoint(self):
        sample_file = resource('random.sample')
        bgen_file = [resource('random-b-disjoint.bgen'), resource('random-c-disjoint.bgen'), resource('random-a-disjoint.bgen')]
        hl.index_bgen(bgen_file)
        with self.assertRaisesRegex(FatalError, 'Each BGEN file must contain a region of the genome disjoint from other files'):
            hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file, n_partitions=3)

    def test_multiple_references_throws_error(self):
        sample_file = resource('random.sample')
        bgen_file1 = resource('random-b.bgen')
        bgen_file2 = resource('random-c.bgen')
        hl.index_bgen(bgen_file1, reference_genome=None)
        hl.index_bgen(bgen_file2, reference_genome='GRCh37')

        with self.assertRaisesRegex(FatalError, 'Found multiple reference genomes were specified in the BGEN index files'):
            hl.import_bgen([bgen_file1, bgen_file2], ['GT'], sample_file=sample_file)

    def test_old_index_file_throws_error(self):
        sample_file = resource('random.sample')
        bgen_file = resource('random.bgen')

        # missing file
        if os.path.exists(bgen_file + '.idx2'):
            run_command(['rm', '-r', bgen_file + '.idx2'])
        with self.assertRaisesRegex(FatalError, 'have no .idx2 index file'):
            hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file, n_partitions=3)

        # old index file
        run_command(['touch', bgen_file + '.idx'])
        with self.assertRaisesRegex(FatalError, 'have no .idx2 index file'):
            hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file)
        run_command(['rm', bgen_file + '.idx'])

    def test_specify_different_index_file(self):
        sample_file = resource('random.sample')
        bgen_file = resource('random.bgen')
        index_file = new_temp_file(suffix='idx2')
        index_file_map = {bgen_file: index_file}
        hl.index_bgen(bgen_file, index_file_map=index_file_map)
        mt = hl.import_bgen(bgen_file, ['GT', 'GP'], sample_file, index_file_map=index_file_map)
        self.assertEqual(mt.count(), (30, 10))

        with self.assertRaisesRegex(FatalError, 'missing a .idx2 file extension'):
            index_file = new_temp_file()
            index_file_map = {bgen_file: index_file}
            hl.index_bgen(bgen_file, index_file_map=index_file_map)

    def test_export_bgen(self):
        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['GP'],
                              sample_file=resource('example.sample'))
        tmp = new_temp_file()
        hl.export_bgen(bgen, tmp)
        hl.index_bgen(tmp + '.bgen')
        bgen2 = hl.import_bgen(tmp + '.bgen',
                               entry_fields=['GP'],
                               sample_file=tmp + '.sample')
        assert bgen._same(bgen2)

    def test_export_bgen_parallel(self):
        bgen = hl.import_bgen(resource('example.8bits.bgen'),
                              entry_fields=['GP'],
                              sample_file=resource('example.sample'),
                              n_partitions=3)
        # tmp = new_temp_file()
        tmp = '/tmp/foo'
        hl.export_bgen(bgen, tmp, parallel='header_per_shard')
        hl.index_bgen(tmp + '.bgen')
        bgen2 = hl.import_bgen(tmp + '.bgen',
                               entry_fields=['GP'],
                               sample_file=tmp + '.sample')
        assert bgen._same(bgen2)

    def test_export_bgen_from_vcf(self):
        mt = hl.import_vcf(resource('sample.vcf'))

        tmp = new_temp_file()
        hl.export_bgen(mt, tmp,
                       gp=hl.or_missing(
                           hl.is_defined(mt.GT),
                           hl.map(lambda i: hl.cond(mt.GT.unphased_diploid_gt_index() == i, 1.0, 0.0),
                                  hl.range(0, hl.triangle(hl.len(mt.alleles))))))
        hl.index_bgen(tmp + '.bgen')
        bgen2 = hl.import_bgen(tmp + '.bgen',
                               entry_fields=['GT'],
                               sample_file=tmp + '.sample')
        mt = mt.select_entries('GT').select_rows().select_cols()
        bgen2 = bgen2.unfilter_entries().select_rows() # drop varid, rsid
        assert bgen2._same(mt)


class GENTests(unittest.TestCase):
    def test_import_gen(self):
        gen = hl.import_gen(resource('example.gen'),
                            sample_file=resource('example.sample'),
                            contig_recoding={"01": "1"},
                            reference_genome = 'GRCh37').rows()
        self.assertTrue(gen.all(gen.locus.contig == "1"))
        self.assertEqual(gen.count(), 199)
        self.assertEqual(gen.locus.dtype, hl.tlocus('GRCh37'))

    def test_import_gen_no_reference_specified(self):
        gen = hl.import_gen(resource('example.gen'),
                            sample_file=resource('example.sample'),
                            reference_genome=None)

        self.assertEqual(gen.locus.dtype,
                         hl.tstruct(contig=hl.tstr, position=hl.tint32))
        self.assertEqual(gen.count_rows(), 199)

    def test_import_gen_skip_invalid_loci(self):
        mt = hl.import_gen(resource('skip_invalid_loci.gen'),
                           resource('skip_invalid_loci.sample'),
                           reference_genome='GRCh37',
                           skip_invalid_loci=True)
        self.assertEqual(mt._force_count_rows(),
                         3)

        with self.assertRaisesRegex(FatalError, 'Invalid locus'):
            hl.import_gen(resource('skip_invalid_loci.gen'),
                          resource('skip_invalid_loci.sample'))

    def test_export_gen(self):
        gen = hl.import_gen(resource('example.gen'),
                            sample_file=resource('example.sample'),
                            contig_recoding={"01": "1"},
                            reference_genome='GRCh37',
                            min_partitions=3)

        # permute columns so not in alphabetical order!
        import random
        indices = list(range(gen.count_cols()))
        random.shuffle(indices)
        gen = gen.choose_cols(indices)

        file = '/tmp/test_export_gen'
        hl.export_gen(gen, file)
        gen2 = hl.import_gen(file + '.gen',
                             sample_file=file + '.sample',
                             reference_genome='GRCh37',
                             min_partitions=3)

        self.assertTrue(gen._same(gen2, tolerance=3E-4, absolute=True))

    def test_export_gen_exprs(self):
        gen = hl.import_gen(resource('example.gen'),
                            sample_file=resource('example.sample'),
                            contig_recoding={"01": "1"},
                            reference_genome='GRCh37',
                            min_partitions=3).add_col_index().add_row_index()

        out1 = new_temp_file()
        hl.export_gen(gen, out1, id1=hl.str(gen.col_idx), id2=hl.str(gen.col_idx), missing=0.5,
                      varid=hl.str(gen.row_idx), rsid=hl.str(gen.row_idx), gp=[0.0, 1.0, 0.0])

        in1 = (hl.import_gen(out1 + '.gen', sample_file=out1 + '.sample', min_partitions=3)
               .add_col_index()
               .add_row_index())
        self.assertTrue(in1.aggregate_entries(hl.agg.fraction((hl.is_missing(in1.GP) | (in1.GP == [0.0, 1.0, 0.0])) == 1.0)))
        self.assertTrue(in1.aggregate_rows(hl.agg.fraction((in1.varid == hl.str(in1.row_idx)) &
                                                           (in1.rsid == hl.str(in1.row_idx)))) == 1.0)
        self.assertTrue(in1.aggregate_cols(hl.agg.fraction((in1.s == hl.str(in1.col_idx)))))


class LocusIntervalTests(unittest.TestCase):
    def test_import_locus_intervals(self):
        interval_file = resource('annotinterall.interval_list')
        t = hl.import_locus_intervals(interval_file, reference_genome='GRCh37')
        nint = t.count()

        i = 0
        with open(interval_file) as f:
            for line in f:
                if len(line.strip()) != 0:
                    i += 1
        self.assertEqual(nint, i)
        self.assertEqual(t.interval.dtype.point_type, hl.tlocus('GRCh37'))

        tmp_file = new_temp_file(prefix="test", suffix="interval_list")
        start = t.interval.start
        end = t.interval.end
        (t
         .key_by(interval=hl.locus_interval(start.contig, start.position, end.position, True, True))
         .select()
         .export(tmp_file, header=False))

        t2 = hl.import_locus_intervals(tmp_file)

        self.assertTrue(t.select()._same(t2))

    def test_import_locus_intervals_no_reference_specified(self):
        interval_file = resource('annotinterall.interval_list')
        t = hl.import_locus_intervals(interval_file, reference_genome=None)
        self.assertEqual(t.count(), 2)
        self.assertEqual(t.interval.dtype.point_type, hl.tstruct(contig=hl.tstr, position=hl.tint32))

    def test_import_locus_intervals_recoding(self):
        interval_file = resource('annotinterall.grch38.no.chr.interval_list')
        t = hl.import_locus_intervals(interval_file,
                                      contig_recoding={str(i): f'chr{i}' for i in [*range(1, 23), 'X', 'Y', 'M']},
                                      reference_genome='GRCh38')
        self.assertEqual(t._force_count(), 3)
        self.assertEqual(t.interval.dtype.point_type, hl.tlocus('GRCh38'))

    def test_import_locus_intervals_badly_defined_intervals(self):
        interval_file = resource('example3.interval_list')
        t = hl.import_locus_intervals(interval_file, reference_genome='GRCh37', skip_invalid_intervals=True)
        self.assertEqual(t.count(), 21)

        t = hl.import_locus_intervals(interval_file, reference_genome=None, skip_invalid_intervals=True)
        self.assertEqual(t.count(), 22)

    def test_import_bed(self):
        bed_file = resource('example1.bed')
        bed = hl.import_bed(bed_file, reference_genome='GRCh37')

        nbed = bed.count()
        i = 0
        with open(bed_file) as f:
            for line in f:
                if len(line.strip()) != 0:
                    try:
                        int(line.split()[0])
                        i += 1
                    except:
                        pass
        self.assertEqual(nbed, i)

        self.assertEqual(bed.interval.dtype.point_type, hl.tlocus('GRCh37'))

        bed_file = resource('example2.bed')
        t = hl.import_bed(bed_file, reference_genome='GRCh37')
        self.assertEqual(t.interval.dtype.point_type, hl.tlocus('GRCh37'))
        self.assertEqual(list(t.key.dtype), ['interval'])
        self.assertEqual(list(t.row.dtype), ['interval','target'])

        expected = [hl.interval(hl.locus('20', 1), hl.locus('20', 11), True, False),   # 20    0 10      gene0
                    hl.interval(hl.locus('20', 2), hl.locus('20', 14000001), True, False),  # 20    1          14000000  gene1
                    hl.interval(hl.locus('20', 5), hl.locus('20', 6), False, False),  # 20    5   5   gene4
                    hl.interval(hl.locus('20', 17000001), hl.locus('20', 18000001), True, False),  # 20    17000000   18000000  gene2
                    hl.interval(hl.locus('20', 63025511), hl.locus('20', 63025520), True, True)]  # 20    63025510   63025520  gene3

        self.assertEqual(t.interval.collect(), hl.eval(expected))

    def test_import_bed_recoding(self):
        bed_file = resource('some-missing-chr-grch38.bed')
        bed = hl.import_bed(bed_file,
                            reference_genome='GRCh38',
                            contig_recoding={str(i): f'chr{i}' for i in [*range(1, 23), 'X', 'Y', 'M']})
        self.assertEqual(bed._force_count(), 5)
        self.assertEqual(bed.interval.dtype.point_type, hl.tlocus('GRCh38'))

    def test_import_bed_no_reference_specified(self):
        bed_file = resource('example1.bed')
        t = hl.import_bed(bed_file, reference_genome=None)
        self.assertEqual(t.count(), 3)
        self.assertEqual(t.interval.dtype.point_type, hl.tstruct(contig=hl.tstr, position=hl.tint32))

    def test_import_bed_kwargs_to_import_table(self):
        bed_file = resource('example2.bed')
        t = hl.import_bed(bed_file, reference_genome='GRCh37', find_replace=('gene', ''))
        self.assertFalse('gene1' in t.aggregate(hl.agg.collect_as_set(t.target)))

    def test_import_bed_badly_defined_intervals(self):
        bed_file = resource('example4.bed')
        t = hl.import_bed(bed_file, reference_genome='GRCh37', skip_invalid_intervals=True)
        self.assertEqual(t.count(), 3)

        t = hl.import_bed(bed_file, reference_genome=None, skip_invalid_intervals=True)
        self.assertEqual(t.count(), 4)

    def test_pass_through_args(self):
        interval_file = resource('example3.interval_list')
        t = hl.import_locus_intervals(interval_file,
                                      reference_genome='GRCh37',
                                      skip_invalid_intervals=True,
                                      filter=r'target_\d\d')
        assert t.count() == 9


class ImportMatrixTableTests(unittest.TestCase):
    @skip_unless_spark_backend()
    def test_import_matrix_table(self):
        mt = hl.import_matrix_table(doctest_resource('matrix1.tsv'),
                                    row_fields={'Barcode': hl.tstr, 'Tissue': hl.tstr, 'Days': hl.tfloat32})
        self.assertEqual(mt['Barcode']._indices, mt._row_indices)
        self.assertEqual(mt['Tissue']._indices, mt._row_indices)
        self.assertEqual(mt['Days']._indices, mt._row_indices)
        self.assertEqual(mt['col_id']._indices, mt._col_indices)
        self.assertEqual(mt['row_id']._indices, mt._row_indices)

        mt.count()

        row_fields = {'f0': hl.tstr, 'f1': hl.tstr, 'f2': hl.tfloat32}
        hl.import_matrix_table(doctest_resource('matrix2.tsv'),
                               row_fields=row_fields, row_key=[]).count()
        hl.import_matrix_table(doctest_resource('matrix3.tsv'),
                               row_fields=row_fields,
                               no_header=True).count()
        hl.import_matrix_table(doctest_resource('matrix3.tsv'),
                               row_fields=row_fields,
                               no_header=True,
                               row_key=[]).count()

    @skip_unless_spark_backend()
    def test_import_matrix_table_no_cols(self):
        fields = {'Chromosome':hl.tstr, 'Position': hl.tint32, 'Ref': hl.tstr, 'Alt': hl.tstr, 'Rand1': hl.tfloat64, 'Rand2': hl.tfloat64}
        file = resource('sample2_va_nomulti.tsv')
        mt = hl.import_matrix_table(file, row_fields=fields, row_key=['Chromosome', 'Position'])
        t = hl.import_table(file, types=fields, key=['Chromosome', 'Position'])

        self.assertEqual(mt.count_cols(), 0)
        self.assertTrue(t._same(mt.rows()))

    def test_headers_not_identical(self):
        self.assertRaisesRegex(
            hl.utils.FatalError,
            "invalid header",
            hl.import_matrix_table,
            resource("sampleheader*.txt"),
            row_fields={'f0': hl.tstr},
            row_key=['f0'])

    def test_too_few_entries(self):
        def boom():
            hl.import_matrix_table(resource("samplesmissing.txt"),
                                   row_fields={'f0': hl.tstr},
                                   row_key=['f0']
            )._force_count_rows()
        self.assertRaisesRegex(
            hl.utils.FatalError,
            "unexpected end of line while reading entry 3",
            boom)

    def test_round_trip(self):
        for missing in ['.', '9']:
            for delimiter in [',', ' ']:
                for header in [True, False]:
                    for entry_type, entry_fun in [(hl.tstr, hl.str),
                                                  (hl.tint32, hl.int32),
                                                  (hl.tfloat64, hl.float64)]:
                        try:
                            self._test_round_trip(missing, delimiter, header, entry_type, entry_fun)
                        except Exception as e:
                            raise ValueError(
                                f'missing {missing!r} delimiter {delimiter!r} '
                                f'header {header!r} entry_type {entry_type!r}'
                            ) from e

    def _test_round_trip(self, missing, delimiter, header, entry_type, entry_fun):
        mt = hl.utils.range_matrix_table(10, 10, n_partitions=2)
        mt = mt.annotate_entries(x = entry_fun(mt.row_idx * mt.col_idx))
        mt = mt.annotate_rows(row_str = hl.str(mt.row_idx))
        mt = mt.annotate_rows(row_float = hl.float(mt.row_idx))

        path = new_temp_file(suffix='tsv')
        mt.key_rows_by(*mt.row).x.export(path,
                                         missing=missing,
                                         delimiter=delimiter,
                                         header=header)

        row_fields = {f: mt.row[f].dtype for f in mt.row}
        row_key = 'row_idx'

        if not header:
            pseudonym = {'row_idx': 'f0',
                         'row_str': 'f1',
                         'row_float': 'f2'}
            row_fields = {pseudonym[k]: v for k, v in row_fields.items()}
            row_key = pseudonym[row_key]
            mt = mt.rename(pseudonym)
        else:
            mt = mt.key_cols_by(col_idx=hl.str(mt.col_idx))

        actual = hl.import_matrix_table(
            path,
            row_fields=row_fields,
            row_key=row_key,
            entry_type=entry_type,
            missing=missing,
            no_header=not header,
            sep=delimiter)
        actual = actual.rename({'col_id': 'col_idx'})

        row_key = mt.row_key
        col_key = mt.col_key
        mt = mt.key_rows_by()
        mt = mt.annotate_entries(
            x = hl.cond(hl.str(mt.x) == missing,
                        hl.null(entry_type),
                        mt.x))
        mt = mt.annotate_rows(**{
            f: hl.cond(hl.str(mt[f]) == missing,
                       hl.null(mt[f].dtype),
                       mt[f])
            for f in mt.row})
        mt = mt.key_rows_by(*row_key)
        assert mt._same(actual)

    def test_key_by_after_empty_key_import(self):
        fields = {'Chromosome':hl.tstr,
                  'Position': hl.tint32,
                  'Ref': hl.tstr,
                  'Alt': hl.tstr}
        mt = hl.import_matrix_table(resource('sample2_va_nomulti.tsv'),
                                    row_fields=fields,
                                    row_key=[],
                                    entry_type=hl.tfloat)
        mt = mt.key_rows_by('Chromosome', 'Position')
        assert 0.001 < abs(0.50965 - mt.aggregate_entries(hl.agg.mean(mt.x)))

    def test_key_by_after_empty_key_import(self):
        fields = {'Chromosome':hl.tstr,
                  'Position': hl.tint32,
                  'Ref': hl.tstr,
                  'Alt': hl.tstr}
        mt = hl.import_matrix_table(resource('sample2_va_nomulti.tsv'),
                                    row_fields=fields,
                                    row_key=[],
                                    entry_type=hl.tfloat)
        mt = mt.key_rows_by('Chromosome', 'Position')
        mt._force_count_rows()

    def test_devlish_nine_separated_eight_missing_file(self):
        fields = {'chr': hl.tstr,
                  '': hl.tint32,
                  'ref': hl.tstr,
                  'alt': hl.tstr}
        mt = hl.import_matrix_table(resource('import_matrix_table_devlish.ninesv'),
                                    row_fields=fields,
                                    row_key=['chr', ''],
                                    sep='9',
                                    missing='8')
        actual = mt.x.collect()
        expected = [
            1, 2, 3, 4,
            11, 12, 13, 14,
            21, 22, 23, 24,
            31, None, None, 34]
        assert actual == expected

        actual = mt.chr.collect()
        assert actual == ['chr1', 'chr1', 'chr1', None]
        actual = mt[''].collect()
        assert actual == [1, 10, 101, None]
        actual = mt.ref.collect()
        assert actual == ['A', 'AGT', None, 'CTA']
        actual = mt.alt.collect()
        assert actual == ['T', 'TGG', 'A', None]


class ImportTableTests(unittest.TestCase):
    def test_import_table_force_bgz(self):
        f = new_temp_file(suffix=".bgz")
        t = hl.utils.range_table(10, 5)
        t.export(f)

        f2 = new_temp_file(suffix=".gz")
        run_command(["cp", uri_path(f), uri_path(f2)])
        t2 = hl.import_table(f2, force_bgz=True, impute=True).key_by('idx')
        self.assertTrue(t._same(t2))

    def test_glob(self):
        tables = hl.import_table(resource('variantAnnotations.split.*.tsv'))
        assert tables.count() == 346
