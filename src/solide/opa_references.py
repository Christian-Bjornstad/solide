"""Laboratory OPA defaults from Variantformatering OPA.xlsx, NM-nummer A1:B45.

Keep these exact versions: this is a reporting list, not a latest/MANE lookup.
"""
OPA_TRANSCRIPTS = {
    'AKT1':'NM_001014431.2', 'AKT2':'NM_001626.6', 'AKT3':'NM_005465.7',
    'ALK':'NM_004304.5', 'AR':'NM_000044.6', 'ARAF':'NM_001654.5',
    'BRAF':'NM_004333.6', 'CDK4':'NM_000075.4', 'CDKN2A':'NM_001195132.1',
    'CHEK2':'NM_007194.4', 'CTNNB1':'NM_001904.4', 'EGFR':'NM_005228.5',
    'ERBB2':'NM_004448.3', 'ERBB3':'NM_001982.4', 'ERBB4':'NM_005235.3',
    'ESR1':'NM_001122740.1', 'FGFR1':'NM_001174067.1', 'FGFR2':'NM_000141.5',
    'FGFR3':'NM_000142.4', 'FGFR4':'NM_213647.3', 'FLT3':'NM_004119.3',
    'GNA11':'NM_002067.5', 'GNAQ':'NM_002072.5', 'GNAS':'NM_000516.6',
    'HRAS':'NM_001130442.2', 'IDH1':'NM_005896.3', 'IDH2':'NM_002168.4',
    'KIT':'NM_000222.3', 'KRAS':'NM_033360.4', 'MAP2K1':'NM_002755.4',
    'MAP2K2':'NM_030662.4', 'MET':'NM_001127500.3', 'MTOR':'NM_004958.4',
    'NRAS':'NM_002524.5', 'NTRK1':'NM_002529.3', 'NTRK2':'NM_006180.5',
    'NTRK3':'NM_001012338.2', 'PDGFRA':'NM_006206.6', 'PIK3CA':'NM_006218.4',
    'PTEN':'NM_000314.8', 'RAF1':'NM_002880.3', 'RET':'NM_020975.6',
    'ROS1':'NM_002944.2', 'SMO':'NM_005631.5', 'TP53':'NM_000546.5',
}


def apply_opa_reference(variant):
    """Supply an omitted c. reference; never replace an explicit source identity."""
    target=OPA_TRANSCRIPTS.get(variant.gene)
    if (not target or variant.corrected_hgvs or variant.raw.get('_annotation_issue')
            or variant.kind.replace(' ','').lower() not in {'snp','snv','del','ins','indel','mnp','complex'}
            or not variant.coding.startswith('c.')):return
    original=variant.transcript
    if original in {'','-','.'}:variant.transcript=target
    if variant.transcript==target:
        variant.raw.setdefault('_opa_reference',{
            'source':'Variantformatering OPA.xlsx / NM-nummer',
            'gene':variant.gene,'transcript':target,'original_transcript':original})


def uses_opa_reference(variant):
    reference=variant.raw.get('_opa_reference',{})
    return (isinstance(reference,dict) and reference.get('gene')==variant.gene
        and reference.get('transcript')==variant.transcript==OPA_TRANSCRIPTS.get(variant.gene))
