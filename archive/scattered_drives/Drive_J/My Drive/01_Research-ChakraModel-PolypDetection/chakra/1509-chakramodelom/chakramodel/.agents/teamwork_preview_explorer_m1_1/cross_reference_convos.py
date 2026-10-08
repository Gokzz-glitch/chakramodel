import json

conv_sums = json.load(open('conversation_summaries.json', 'r', encoding='utf-8'))
om_convs = json.load(open('OM_rama_krish_convo.json', 'r', encoding='utf-8'))

print("conv_sums len:", len(conv_sums))
print("om_convs len:", len(om_convs))

# Check matching IDs
sum_ids = {d['conversation_id']: d for d in conv_sums}
om_ids = {d['conversation_id']: d for d in om_convs}

overlap = set(sum_ids.keys()) & set(om_ids.keys())
print("Overlapping conversation IDs:", len(overlap))
