from solide._vendor.archer.services.database_search import DatabaseSearchService


def test_clinvar_uses_variant_aggregate_not_first_condition_or_submission():
    xml=b'''<ClinVarResult-Set><VariationArchive Accession="VCV000000001" Version="2">
      <ClassifiedRecord><RCVList><RCVAccession><Classifications><GermlineClassification>
        <Description>Pathogenic</Description></GermlineClassification></Classifications></RCVAccession></RCVList>
      <Classifications><GermlineClassification><Description>Conflicting classifications of pathogenicity</Description>
        <ReviewStatus>criteria provided, conflicting classifications</ReviewStatus></GermlineClassification>
        <SomaticClinicalImpact><Description>Tier I - Strong</Description></SomaticClinicalImpact>
        <OncogenicityClassification><Description>Oncogenic</Description></OncogenicityClassification></Classifications>
      </ClassifiedRecord><ClinicalAssertionList><ClinicalAssertion><ClinicalSignificance>
        <Description>Benign</Description></ClinicalSignificance></ClinicalAssertion></ClinicalAssertionList>
    </VariationArchive></ClinVarResult-Set>'''
    result=DatabaseSearchService()._parse_clinvar(xml,'NM_1.1:c.1A>T','1')
    assert result.clinical_significance=='Conflicting classifications of pathogenicity'
    assert result.raw['classifications']=={'germline':'Conflicting classifications of pathogenicity',
        'somatic_clinical_impact':'Tier I - Strong','oncogenicity':'Oncogenic'}
    assert 'conflicting classifications' in result.summary


def test_missing_aggregate_does_not_promote_an_individual_submission():
    xml=b'''<VariationArchive><ClassifiedRecord><ClinicalAssertionList><ClinicalAssertion>
        <GermlineClassification><Description>Pathogenic</Description></GermlineClassification>
        </ClinicalAssertion></ClinicalAssertionList></ClassifiedRecord></VariationArchive>'''
    result=DatabaseSearchService()._parse_clinvar(xml,'query','1')
    assert result.clinical_significance=='' and result.raw['classifications']=={}


def test_legacy_rcv_aggregate_remains_supported():
    xml=b'''<ClinVarSet><ReferenceClinVarAssertion><ClinicalSignificance>
        <Description>Likely pathogenic</Description><ReviewStatus>reviewed by expert panel</ReviewStatus>
        </ClinicalSignificance></ReferenceClinVarAssertion></ClinVarSet>'''
    result=DatabaseSearchService()._parse_clinvar(xml,'query','1')
    assert result.clinical_significance=='Likely pathogenic'
