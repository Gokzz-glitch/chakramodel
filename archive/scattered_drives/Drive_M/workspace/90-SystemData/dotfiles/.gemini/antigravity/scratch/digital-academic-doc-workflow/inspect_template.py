from pptx import Presentation

prs = Presentation(r"J:\My Drive\downloads\Project_Review_PPT_Template.pptx")
for i, layout in enumerate(prs.slide_layouts):
    print(f"Layout {i}: {layout.name}")
    for shape in layout.placeholders:
        print(f"  Placeholder {shape.placeholder_format.idx}: {shape.name}")
