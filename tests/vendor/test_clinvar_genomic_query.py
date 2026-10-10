from pathlib import Path
from types import SimpleNamespace

import pytest

from solide._vendor.archer.core.models import VariantRecord,DatabaseEvidence
from solide._vendor.archer.services.database_search import DatabaseSearchService


@pytest.mark.parametrize('returned_alt,expected_status',[('A','found'),('T','not_found')])
def test_genomic_only_clinvar_search_verifies_returned_allele(monkeypatch,returned_alt,expected_status):
    service=DatabaseSearchService()
    record=VariantRecord(Path('source.tsv'),1,'SOURCE','TP53','',genomic_location='chr17:7578406',
                         ref_allele='G',alt_allele='A')
    terms=[]
    def request(url,params):
        if 'esearch' in url:
            terms.append(params['term']);content=b'<Result><IdList><Id>1</Id></IdList></Result>'
        else:
            content=(f'<Result><SequenceLocation Assembly="GRCh37" Chr="17" positionVCF="7578406" '
                     f'referenceAlleleVCF="G" alternateAlleleVCF="{returned_alt}"/></Result>').encode()
        return SimpleNamespace(content=content,raise_for_status=lambda:None)
    monkeypatch.setattr(service,'_eutils_get',request)
    monkeypatch.setattr(service,'_parse_clinvar',lambda *args:DatabaseEvidence('ClinVar','found'))
    result=service._search_clinvar(record)
    assert result.status==expected_status
    assert terms==['17[chr] AND 7578406[chrpos37]']
    if expected_status=='found':assert result.raw['matched_location']['alternate']=='A'
