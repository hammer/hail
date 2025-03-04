.. _sec-functions:

Functions
=========

These functions are exposed at the top level of the module, e.g. ``hl.case``.

.. currentmodule:: hail.expr.functions

.. toctree::
    :maxdepth: 2

    core
    constructors
    collections
    numeric
    string
    stats
    random
    genetics

.. rubric:: Core language functions

.. autosummary::

    eval
    literal
    cond
    switch
    case
    bind
    rbind
    null
    is_missing
    is_defined
    coalesce
    or_else
    or_missing
    range

.. rubric:: Constructors

.. autosummary::

    bool
    float
    float32
    float64
    int
    int32
    int64
    interval
    str
    struct
    tuple

.. rubric:: Collection constructors

.. autosummary::

    array
    empty_array
    set
    empty_set
    dict

.. rubric:: Collection functions

.. autosummary::

    len
    map
    flatmap
    zip
    zip_with_index
    flatten
    any
    all
    filter
    sorted
    find
    group_by
    fold
    array_scan
    reversed

.. rubric:: Numeric functions

.. autosummary::

    abs
    approx_equal
    bit_and
    bit_or
    bit_xor
    bit_lshift
    bit_rshift
    bit_not
    exp
    is_nan
    is_finite
    is_infinite
    log
    log10
    sign
    sqrt
    int
    int32
    int64
    float
    float32
    float64
    floor
    ceil
    uniroot

.. rubric:: Numeric collection functions

.. autosummary::

    min
    nanmin
    max
    nanmax
    mean
    median
    product
    sum
    cumulative_sum
    argmin
    argmax
    corr
    binary_search

.. rubric:: String functions

.. autosummary::

    format
    json
    hamming
    delimit
    entropy

.. rubric:: Statistical functions

.. autosummary::

    chi_squared_test
    fisher_exact_test
    contingency_table_test
    dbeta
    dpois
    hardy_weinberg_test
    pchisqtail
    pnorm
    ppois
    qchisqtail
    qnorm
    qpois

.. rubric:: Randomness

.. autosummary::

    rand_bool
    rand_beta
    rand_cat
    rand_dirichlet
    rand_gamma
    rand_norm
    rand_pois
    rand_unif

.. rubric:: Genetics functions

.. autosummary::

    locus
    locus_from_global_position
    locus_interval
    parse_locus
    parse_variant
    parse_locus_interval
    variant_str
    call
    unphased_diploid_gt_index_call
    parse_call
    downcode
    triangle
    is_snp
    is_mnp
    is_transition
    is_transversion
    is_insertion
    is_deletion
    is_indel
    is_star
    is_complex
    is_valid_contig
    is_valid_locus
    allele_type
    pl_dosage
    gp_dosage
    get_sequence
    mendel_error_code
    liftover
    min_rep
