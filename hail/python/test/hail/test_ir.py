import unittest
import hail as hl
import hail.ir as ir
from hail.ir.renderer import CSERenderer
from hail.expr import construct_expr
from hail.expr.types import tint32
from hail.utils.java import Env
from hail.utils import new_temp_file
from .helpers import *

setUpModule = startTestHailContext
tearDownModule = stopTestHailContext


class ValueIRTests(unittest.TestCase):
    def value_irs(self):
        b = ir.TrueIR()
        c = ir.Ref('c')
        i = ir.I32(5)
        j = ir.I32(7)
        st = ir.Str('Hail')
        a = ir.Ref('a')
        aa = ir.Ref('aa')
        da = ir.Ref('da')
        nd = ir.Ref('nd')
        v = ir.Ref('v')
        s = ir.Ref('s')
        t = ir.Ref('t')
        call = ir.Ref('call')

        table = ir.TableRange(5, 3)

        matrix_read = ir.MatrixRead(ir.MatrixNativeReader(
            resource('backward_compatability/1.0.0/matrix_table/0.hmt'), None, False),
            False, False)

        block_matrix_read = ir.BlockMatrixRead(ir.BlockMatrixNativeReader('fake_file_path'))

        value_irs = [
            i, ir.I64(5), ir.F32(3.14), ir.F64(3.14), s, ir.TrueIR(), ir.FalseIR(), ir.Void(),
            ir.Cast(i, hl.tfloat64),
            ir.NA(hl.tint32),
            ir.IsNA(i),
            ir.If(b, i, j),
            ir.Coalesce(i, j),
            ir.Let('v', i, v),
            ir.Ref('x'),
            ir.ApplyBinaryPrimOp('+', i, j),
            ir.ApplyUnaryPrimOp('-', i),
            ir.ApplyComparisonOp('EQ', i, j),
            ir.MakeArray([i, ir.NA(hl.tint32), ir.I32(-3)], hl.tarray(hl.tint32)),
            ir.ArrayRef(a, i),
            ir.ArrayLen(a),
            ir.ArrayRange(ir.I32(0), ir.I32(5), ir.I32(1)),
            ir.ArraySort(a, 'l', 'r', ir.ApplyComparisonOp("LT", ir.Ref('l'), ir.Ref('r'))),
            ir.ToSet(a),
            ir.ToDict(da),
            ir.ToArray(a),
            ir.MakeNDArray(ir.MakeArray([ir.F64(-1.0), ir.F64(1.0)], hl.tarray(hl.tfloat64)),
                           ir.MakeTuple([ir.I64(1), ir.I64(2)]),
                           ir.TrueIR()),
            ir.NDArrayShape(nd),
            ir.NDArrayReshape(nd, ir.MakeTuple([ir.I64(5)])),
            ir.NDArrayRef(nd, [ir.I64(1), ir.I64(2)]),
            ir.NDArrayMap(nd, 'v', v),
            ir.NDArrayMatMul(nd, nd),
            ir.LowerBoundOnOrderedCollection(a, i, True),
            ir.GroupByKey(da),
            ir.ArrayMap(a, 'v', v),
            ir.ArrayFilter(a, 'v', v),
            ir.ArrayFlatMap(aa, 'v', v),
            ir.ArrayFold(a, ir.I32(0), 'x', 'v', v),
            ir.ArrayScan(a, ir.I32(0), 'x', 'v', v),
            ir.ArrayLeftJoinDistinct(a, a, 'l', 'r', ir.I32(0), ir.I32(1)),
            ir.ArrayFor(a, 'v', ir.Void()),
            ir.AggFilter(ir.TrueIR(), ir.I32(0), False),
            ir.AggExplode(ir.ArrayRange(ir.I32(0), ir.I32(2), ir.I32(1)), 'x', ir.I32(0), False),
            ir.AggGroupBy(ir.TrueIR(), ir.I32(0), False),
            ir.AggArrayPerElement(ir.ArrayRange(ir.I32(0), ir.I32(2), ir.I32(1)), 'x', 'y', ir.I32(0), False),
            ir.ApplyAggOp('Collect', [], None, [ir.I32(0)]),
            ir.ApplyScanOp('Collect', [], None, [ir.I32(0)]),
            ir.ApplyAggOp('CallStats', [], [ir.I32(2)], [call]),
            ir.ApplyAggOp('TakeBy', [ir.I32(10)], None, [ir.F64(-2.11), ir.F64(-2.11)]),
            ir.Begin([ir.Void()]),
            ir.MakeStruct([('x', i)]),
            ir.SelectFields(s, ['x', 'z']),
            ir.InsertFields(s, [('x', i)], None),
            ir.GetField(s, 'x'),
            ir.MakeTuple([i, b]),
            ir.GetTupleElement(t, 1),
            ir.In(2, hl.tfloat64),
            ir.Die(ir.Str('mumblefoo'), hl.tfloat64),
            ir.Apply('&&', hl.tbool, b, c),
            ir.Apply('toFloat64', hl.tfloat64, i),
            ir.Uniroot('x', ir.F64(3.14), ir.F64(-5.0), ir.F64(5.0)),
            ir.Literal(hl.tarray(hl.tint32), [1, 2, None]),
            ir.TableCount(table),
            ir.TableGetGlobals(table),
            ir.TableCollect(table),
            ir.TableToValueApply(table, {'name': 'ForceCountTable'}),
            ir.MatrixToValueApply(matrix_read, {'name': 'ForceCountMatrixTable'}),
            ir.TableAggregate(table, ir.MakeStruct([('foo', ir.ApplyAggOp('Collect', [], None, [ir.I32(0)]))])),
            ir.TableWrite(table, ir.TableNativeWriter(new_temp_file(), False, True, "fake_codec_spec$$")),
            ir.TableWrite(table, ir.TableTextWriter(new_temp_file(), None, True, 0, ",")),
            ir.MatrixAggregate(matrix_read, ir.MakeStruct([('foo', ir.ApplyAggOp('Collect', [], None, [ir.I32(0)]))])),
            ir.MatrixWrite(matrix_read, ir.MatrixNativeWriter(new_temp_file(), False, False, "", None, None)),
            ir.MatrixWrite(matrix_read, ir.MatrixNativeWriter(new_temp_file(), False, False, "",
                                                              '[{"start":{"row_idx":0},"end":{"row_idx": 10},"includeStart":true,"includeEnd":false}]',
                                                              hl.dtype('array<interval<struct{row_idx:int32}>>'))),
            ir.MatrixWrite(matrix_read, ir.MatrixVCFWriter(new_temp_file(), None, False, None)),
            ir.MatrixWrite(matrix_read, ir.MatrixGENWriter(new_temp_file(), 4)),
            ir.MatrixWrite(matrix_read, ir.MatrixPLINKWriter(new_temp_file())),
            ir.MatrixMultiWrite([matrix_read, matrix_read], ir.MatrixNativeMultiWriter(new_temp_file(), False, False)),
            ir.BlockMatrixWrite(block_matrix_read, ir.BlockMatrixNativeWriter('fake_file_path', False, False, False))
        ]

        return value_irs

    def test_parses(self):
        env = {'c': hl.tbool,
               'a': hl.tarray(hl.tint32),
               'aa': hl.tarray(hl.tarray(hl.tint32)),
               'da': hl.tarray(hl.ttuple(hl.tint32, hl.tstr)),
               'nd': hl.tndarray(hl.tfloat64, 1),
               'v': hl.tint32,
               's': hl.tstruct(x=hl.tint32, y=hl.tint64, z=hl.tfloat64),
               't': hl.ttuple(hl.tint32, hl.tint64, hl.tfloat64),
               'call': hl.tcall,
               'x': hl.tint32}
        env = {name: t._parsable_string() for name, t in env.items()}
        for x in self.value_irs():
            Env.hail().expr.ir.IRParser.parse_value_ir(str(x), env, {})

    def test_copies(self):
        for x in self.value_irs():
            cp = x.copy(*x.children)
            assert x == cp
            assert hash(x) == hash(cp)


class TableIRTests(unittest.TestCase):

    def table_irs(self):
        b = ir.TrueIR()
        table_read = ir.TableRead(
            ir.TableNativeReader(resource('backward_compatability/1.0.0/table/0.ht'), None, False), False)
        table_read_row_type = hl.dtype('struct{idx: int32, f32: float32, i64: int64, m: float64, astruct: struct{a: int32, b: float64}, mstruct: struct{x: int32, y: str}, aset: set<str>, mset: set<float64>, d: dict<array<str>, float64>, md: dict<int32, str>, h38: locus<GRCh38>, ml: locus<GRCh37>, i: interval<locus<GRCh37>>, c: call, mc: call, t: tuple(call, str, str), mt: tuple(locus<GRCh37>, bool)}')

        matrix_read = ir.MatrixRead(
            ir.MatrixNativeReader(resource('backward_compatability/1.0.0/matrix_table/0.hmt'), None, False),
            False, False)

        block_matrix_read = ir.BlockMatrixRead(ir.BlockMatrixNativeReader('fake_file_path'))

        aa = hl.literal([[0.00],[0.01],[0.02]])._ir

        range = ir.TableRange(10, 4)
        table_irs = [
            ir.TableKeyBy(table_read, ['m', 'd'], False),
            ir.TableFilter(table_read, b),
            table_read,
            ir.MatrixColsTable(matrix_read),
            ir.TableAggregateByKey(
                table_read,
                ir.MakeStruct([('a', ir.I32(5))])),
            ir.TableKeyByAndAggregate(
                table_read,
                ir.MakeStruct([('a', ir.I32(5))]),
                ir.MakeStruct([('b', ir.I32(5))]),
                1, 2),
            ir.TableJoin(
                table_read,
                ir.TableRange(100, 10), 'inner', 1),
            ir.MatrixEntriesTable(matrix_read),
            ir.MatrixRowsTable(matrix_read),
            ir.TableParallelize(ir.MakeStruct([
                ('rows', ir.Literal(hl.tarray(hl.tstruct(a=hl.tint32)), [{'a':None}, {'a':5}, {'a':-3}])),
                ('global', ir.MakeStruct([]))]), None),
            ir.TableMapRows(
                ir.TableKeyBy(table_read, []),
                ir.MakeStruct([
                    ('a', ir.GetField(ir.Ref('row'), 'f32')),
                    ('b', ir.F64(-2.11))])),
            ir.TableMapGlobals(
                table_read,
                ir.MakeStruct([
                    ('foo', ir.NA(hl.tarray(hl.tint32)))])),
            ir.TableRange(100, 10),
            ir.TableRepartition(table_read, 10, ir.RepartitionStrategy.COALESCE),
            ir.TableUnion(
                [ir.TableRange(100, 10), ir.TableRange(50, 10)]),
            ir.TableExplode(table_read, ['mset']),
            ir.TableHead(table_read, 10),
            ir.TableOrderBy(ir.TableKeyBy(table_read, []), [('m', 'A'), ('m', 'D')]),
            ir.TableDistinct(table_read),
            ir.CastMatrixToTable(matrix_read, '__entries', '__cols'),
            ir.TableRename(table_read, {'idx': 'idx_foo'}, {'global_f32': 'global_foo'}),
            ir.TableMultiWayZipJoin([table_read, table_read], '__data', '__globals'),
            ir.MatrixToTableApply(matrix_read, {'name': 'LinearRegressionRowsSingle', 'yFields': ['col_m'], 'xField': 'entry_m', 'covFields': [], 'rowBlockSize': 10, 'passThrough': []}),
            ir.TableToTableApply(table_read, {'name': 'TableFilterPartitions', 'parts': [0], 'keep': True}),
            ir.BlockMatrixToTableApply(block_matrix_read, aa, {'name': 'PCRelate', 'maf': 0.01, 'blockSize': 4096}),
            ir.TableFilterIntervals(table_read, [hl.utils.Interval(hl.utils.Struct(row_idx=0), hl.utils.Struct(row_idx=10))], hl.tstruct(row_idx=hl.tint32), keep=False),
        ]

        return table_irs

    def test_parses(self):
        for x in self.table_irs():
            Env.hail().expr.ir.IRParser.parse_table_ir(str(x))


class MatrixIRTests(unittest.TestCase):
    def matrix_irs(self):
        hl.index_bgen(resource('example.8bits.bgen'),
                      reference_genome=hl.get_reference('GRCh37'),
                      contig_recoding={'01': '1'})

        collect = ir.MakeStruct([('x', ir.ApplyAggOp('Collect', [], None, [ir.I32(0)]))])

        matrix_read = ir.MatrixRead(
            ir.MatrixNativeReader(
                resource('backward_compatability/1.0.0/matrix_table/0.hmt'), None, False),
            False, False)
        table_read = ir.TableRead(
            ir.TableNativeReader(resource('backward_compatability/1.0.0/table/0.ht'), None, False), False)

        matrix_range = ir.MatrixRead(ir.MatrixRangeReader(1, 1, 10))
        matrix_irs = [
            ir.MatrixRepartition(matrix_range, 100, ir.RepartitionStrategy.SHUFFLE),
            ir.MatrixUnionRows(matrix_range, matrix_range),
            ir.MatrixDistinctByRow(matrix_range),
            ir.MatrixRowsHead(matrix_read, 5),
            ir.MatrixColsHead(matrix_read, 5),
            ir.CastTableToMatrix(
                ir.CastMatrixToTable(matrix_read, '__entries', '__cols'),
                '__entries',
                '__cols',
                []),
            ir.MatrixAggregateRowsByKey(matrix_read, collect, collect),
            ir.MatrixAggregateColsByKey(matrix_read, collect, collect),
            matrix_read,
            matrix_range,
            ir.MatrixRead(ir.MatrixVCFReader(resource('sample.vcf'), ['GT'], hl.tfloat64, None, None, None, None,
                                             False, True, False, True, None, None, None)),
            ir.MatrixRead(ir.MatrixBGENReader(resource('example.8bits.bgen'), None, {}, 10, 1, None)),
            ir.MatrixFilterRows(matrix_read, ir.FalseIR()),
            ir.MatrixFilterCols(matrix_read, ir.FalseIR()),
            ir.MatrixFilterEntries(matrix_read, ir.FalseIR()),
            ir.MatrixChooseCols(matrix_read, [1, 0]),
            ir.MatrixMapCols(matrix_read, ir.MakeStruct([('x', ir.I64(20))]), ['x']),
            ir.MatrixKeyRowsBy(matrix_read, ['row_i64'], False),
            ir.MatrixMapRows(ir.MatrixKeyRowsBy(matrix_read, []), ir.MakeStruct([('x', ir.I64(20))])),
            ir.MatrixMapEntries(matrix_read, ir.MakeStruct([('x', ir.I64(20))])),
            ir.MatrixMapGlobals(matrix_read, ir.MakeStruct([('x', ir.I64(20))])),
            ir.MatrixCollectColsByKey(matrix_read),
            ir.MatrixExplodeRows(matrix_read, ['row_aset']),
            ir.MatrixExplodeCols(matrix_read, ['col_aset']),
            ir.MatrixAnnotateRowsTable(matrix_read, table_read, '__foo'),
            ir.MatrixAnnotateColsTable(matrix_read, table_read, '__foo'),
            ir.MatrixToMatrixApply(matrix_read, {'name': 'MatrixFilterPartitions', 'parts': [0], 'keep': True}),
            ir.MatrixRename(matrix_read, {'global_f32': 'global_foo'}, {'col_f32': 'col_foo'}, {'row_aset': 'row_aset2'}, {'entry_f32': 'entry_foo'}),
            ir.MatrixFilterIntervals(matrix_read, [hl.utils.Interval(hl.utils.Struct(row_idx=0), hl.utils.Struct(row_idx=10))], hl.tstruct(row_idx=hl.tint32), keep=False),
        ]

        return matrix_irs

    def test_parses(self):
        for x in self.matrix_irs():
            try:
                Env.hail().expr.ir.IRParser.parse_matrix_ir(str(x))
            except Exception as e:
                raise ValueError(str(x)) from e

    def test_highly_nested_ir(self):
        N = 10
        M = 250
        ht = hl.utils.range_table(N)
        for i in range(M):
            ht = ht.annotate(**{f'x{i}': i})
        str(ht._tir)

        # TODO: Scala Pretty errors out with a StackOverflowError here
        # ht._force_count()


class BlockMatrixIRTests(unittest.TestCase):
    def blockmatrix_irs(self):
        scalar_ir = ir.F64(2)
        vector_ir = ir.MakeArray([ir.F64(3), ir.F64(2)], hl.tarray(hl.tfloat64))

        read = ir.BlockMatrixRead(ir.BlockMatrixNativeReader(resource('blockmatrix_example/0')))
        add_two_bms = ir.BlockMatrixMap2(read, read, ir.ApplyBinaryPrimOp('+', ir.Ref('l'), ir.Ref('r')))
        negate_bm = ir.BlockMatrixMap(read, ir.ApplyUnaryPrimOp('-', ir.Ref('element')))
        sqrt_bm = ir.BlockMatrixMap(read, hl.sqrt(construct_expr(ir.Ref('element'), hl.tfloat64))._ir)

        scalar_to_bm = ir.ValueToBlockMatrix(scalar_ir, [1, 1], 1)
        col_vector_to_bm = ir.ValueToBlockMatrix(vector_ir, [2, 1], 1)
        row_vector_to_bm = ir.ValueToBlockMatrix(vector_ir, [1, 2], 1)
        broadcast_scalar = ir.BlockMatrixBroadcast(scalar_to_bm, [], [2, 2], 256)
        broadcast_col = ir.BlockMatrixBroadcast(col_vector_to_bm, [0], [2, 2], 256)
        broadcast_row = ir.BlockMatrixBroadcast(row_vector_to_bm, [1], [2, 2], 256)
        transpose = ir.BlockMatrixBroadcast(broadcast_scalar, [1, 0], [2, 2], 256)
        matmul = ir.BlockMatrixDot(broadcast_scalar, transpose)

        pow_ir = (construct_expr(ir.Ref('l'), hl.tfloat64) ** construct_expr(ir.Ref('r'), hl.tfloat64))._ir
        squared_bm = ir.BlockMatrixMap2(scalar_to_bm, scalar_to_bm, pow_ir)
        slice_bm = ir.BlockMatrixSlice(matmul, [slice(0, 2, 1), slice(0, 1, 1)])

        return [
            read,
            add_two_bms,
            negate_bm,
            sqrt_bm,
            scalar_to_bm,
            col_vector_to_bm,
            row_vector_to_bm,
            broadcast_scalar,
            broadcast_col,
            broadcast_row,
            squared_bm,
            transpose,
            matmul,
            slice_bm
        ]

    def test_parses(self):
        for x in self.blockmatrix_irs():
            Env.hail().expr.ir.IRParser.parse_blockmatrix_ir(str(x))


class ValueTests(unittest.TestCase):

    def values(self):
        values = [
            (hl.tbool, True),
            (hl.tint32, 0),
            (hl.tint64, 0),
            (hl.tfloat32, 0.5),
            (hl.tfloat64, 0.5),
            (hl.tstr, "foo"),
            (hl.tstruct(x=hl.tint32), hl.Struct(x=0)),
            (hl.tarray(hl.tint32), [0, 1, 4]),
            (hl.tset(hl.tint32), {0, 1, 4}),
            (hl.tdict(hl.tstr, hl.tint32), {"a": 0, "b": 1, "c": 4}),
            (hl.tinterval(hl.tint32), hl.Interval(0, 1, True, False)),
            (hl.tlocus(hl.default_reference()), hl.Locus("1", 1)),
            (hl.tcall, hl.Call([0, 1]))
        ]
        return values

    def test_value_same_after_parsing(self):
        for t, v in self.values():
            row_v = ir.Literal(t, v)
            map_globals_ir = ir.TableMapGlobals(
                ir.TableRange(1, 1),
                ir.InsertFields(
                    ir.Ref("global"),
                    [("foo", row_v)],
                    None))
            new_globals = hl.eval(hl.Table(map_globals_ir).index_globals())
            self.assertEqual(new_globals, hl.Struct(foo=v))


class CSETests(unittest.TestCase):
    def test_cse(self):
        x = ir.I32(5)
        x = ir.ApplyBinaryPrimOp('+', x, x)
        expected = (
            '(Let __cse_1 (I32 5)'
            ' (ApplyBinaryPrimOp `+`'
                ' (Ref __cse_1)'
                ' (Ref __cse_1)))')
        assert expected == CSERenderer()(x)

    def test_cse2(self):
        x = ir.I32(5)
        y = ir.I32(4)
        sum = ir.ApplyBinaryPrimOp('+', x, x)
        prod = ir.ApplyBinaryPrimOp('*', sum, y)
        div = ir.ApplyBinaryPrimOp('/', prod, sum)
        expected = (
            '(Let __cse_1 (I32 5)'
            ' (Let __cse_2 (ApplyBinaryPrimOp `+` (Ref __cse_1) (Ref __cse_1))'
            ' (ApplyBinaryPrimOp `/`'
                ' (ApplyBinaryPrimOp `*`'
                    ' (Ref __cse_2)'
                    ' (I32 4))'
                ' (Ref __cse_2))))')
        assert expected == CSERenderer()(div)

    def test_cse_ifs(self):
        outer_repeated = ir.I32(5)
        inner_repeated = ir.I32(1)
        sum = ir.ApplyBinaryPrimOp('+', inner_repeated, inner_repeated)
        prod = ir.ApplyBinaryPrimOp('*', sum, outer_repeated)
        cond = ir.If(ir.TrueIR(), prod, outer_repeated)
        expected = (
            '(If (True)'
                ' (Let __cse_1 (I32 1)'
                ' (ApplyBinaryPrimOp `*`'
                    ' (ApplyBinaryPrimOp `+` (Ref __cse_1) (Ref __cse_1))'
                    ' (I32 5)))'
                ' (I32 5))'
        )
        assert expected == CSERenderer()(cond)

    def test_agg_cse(self):
        x = ir.GetField(ir.Ref('row'), 'idx')
        inner_sum = ir.ApplyBinaryPrimOp('+', x, x)
        agg = ir.ApplyAggOp('AggOp', [], [], [inner_sum])
        outer_sum = ir.ApplyBinaryPrimOp('+', agg, agg)
        table_agg = ir.TableAggregate(ir.TableRange(5, 1), outer_sum)
        expected = (
            '(TableAggregate (TableRange 5 1)'
                ' (AggLet __cse_1 False (GetField idx (Ref row))'
                ' (Let __cse_2 (ApplyAggOp AggOp () None'
                    ' ((ApplyBinaryPrimOp `+` (Ref __cse_1) (Ref __cse_1))))'
                ' (ApplyBinaryPrimOp `+` (Ref __cse_2) (Ref __cse_2)))))')
        assert expected == CSERenderer()(table_agg)

    def test_init_op(self):
        x = ir.I32(5)
        sum = ir.ApplyBinaryPrimOp('+', x, x)
        agg = ir.ApplyAggOp('CallStats', [sum], [sum], [sum])
        top = ir.ApplyBinaryPrimOp('+', sum, agg)
        expected = (
            '(Let __cse_1 (I32 5)'
            ' (AggLet __cse_4 False (I32 5)'
            ' (ApplyBinaryPrimOp `+`'
                ' (ApplyBinaryPrimOp `+` (Ref __cse_1) (Ref __cse_1))'
                ' (ApplyAggOp CallStats'
                    ' ((Let __cse_3 (I32 5)'
                        ' (ApplyBinaryPrimOp `+` (Ref __cse_3) (Ref __cse_3))))'
                    ' ((Let __cse_3 (I32 5)'
                        ' (ApplyBinaryPrimOp `+` (Ref __cse_3) (Ref __cse_3))))'
                    ' ((ApplyBinaryPrimOp `+` (Ref __cse_4) (Ref __cse_4)))))))')
        assert expected == CSERenderer()(top)
