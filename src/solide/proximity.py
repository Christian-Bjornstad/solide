"""Selected nearby sequence events that warrant an IGV phasing check."""
from collections import defaultdict
from ._vendor.archer.services.genomic_notation import normalize_vcf_change

IGV_DISTANCE_BP=100


def nearby_variants(variants,distance=IGV_DISTANCE_BP):
    groups=defaultdict(lambda:defaultdict(list));result=defaultdict(list)
    for v in variants:
        if (not v.selected or v.assembly!='GRCh37' or not v.gene or ',' in v.gene
                or v.kind.replace(' ','').lower() in {'cnv','fusion','rnaexontiles','rnaexonvariant'}):continue
        event=normalize_vcf_change(v.locus,v.ref,v.alt)
        if event is None:continue
        # Different interpretations of the exact same DNA event are not a pair.
        key=(v.analysis_id or v.patient,v.patient,v.gene.upper(),v.assembly,event.chromosome)
        groups[key][event].append(v)
    for events in groups.values():
        entries=sorted(events.items(),key=lambda pair:pair[0].start)
        for i,(first,first_rows) in enumerate(entries):
            for second,second_rows in entries[i+1:]:
                gap=max(0,second.start-first.end)
                if gap>distance:break
                for a in first_rows:result[a.id].append((second_rows[0],gap))
                for b in second_rows:result[b.id].append((first_rows[0],gap))
    return dict(result)


def igv_message(v,neighbours):
    details=', '.join(f'{other.coding or other.locus} ({gap} bp)' for other,gap in neighbours)
    return f'Sjekk IGV: nærliggende varianter i {v.gene}: {details}. Vurder om de ligger i cis/på samme allel.'
