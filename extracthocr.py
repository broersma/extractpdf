import xml.etree.cElementTree as ET,re,string

# a function for extracting the text from a node

def get_text(node):
    textnodes = node.findall(".//")
    s = string.join([node.text for node in textnodes if node.text is not None])
    return re.sub(r'\s+',' ',s)

# a function for extracting the bbox property from a node
# note that the title= attribute on a node with an ocr_ class must
# conform with the OCR spec

def get_bbox(node):
    data = node.attrib.get('title')
    bboxre = re.compile(r'\bbbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)')
    return [int(x) for x in bboxre.search(data).groups()]

def get_bbox_texts(filename):
    # parse the XML

    doc = ET.parse(filename)

    # search all nodes having a class of ocr_line

    lines = doc.findall(".//*[@class='ocr_line']")

    # this extracts all the bounding boxes and the text they contain
    # it doesn't matter what other markup the line node may contain
    for line in lines:
        bbox = get_bbox(line)
        yield {
        "x0": bbox[0],
        "y0": bbox[1],
        "x1": bbox[2],
        "y1": bbox[3],
        "fontname": 'unknown', # default = 'unknown'
        "fontsize": 0,         # default = 0
        "orientation": 'H',    # default = H
        "text": get_text(line)}

def get_bbox_page(filename):
    # convert the HTML to XHTML (if necessary)

    #os.system("tidy -q -asxhtml < page.html > page.xhtml 2> /dev/null")

    # parse the XML

    doc = ET.parse(filename)

    # search all nodes having a class of ocr_line

    page = doc.find(".//*[@class='ocr_page']")

    # this extracts all the bounding boxes and the text they contain
    # it doesn't matter what other markup the line node may contain
    bbox = get_bbox(page)
    return (
    bbox[0],
    bbox[1],
    bbox[2],
    bbox[3])