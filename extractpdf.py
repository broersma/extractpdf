#!/usr/bin/python
import multiprocessing
import logging


filename_filter = "*.pdf"
filename_output = "result.json"
max_processes = 2
output_lock = multiprocessing.Lock()
logging.getLogger().setLevel(logging.INFO)


def get_result_from_file(filename):
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfpage import PDFTextExtractionNotAllowed
    from pdfminer.pdfinterp import PDFResourceManager
    from pdfminer.pdfinterp import PDFPageInterpreter
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LAParams

    result = {"filename": filename, "pages": []}
    fp = open(filename, 'rb')
    parser = PDFParser(fp)
    document = PDFDocument(parser)
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    laparams.char_margin = 2.0
    laparams.detect_vertical = True
    laparams.line_margin = 1.0
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    page_index = 0
    for page in PDFPage.create_pages(document):
        interpreter.process_page(page)
        layout = device.get_result()
        bounding_box = get_bounding_box(layout)
        labels = get_text_labels(layout)
        result["pages"].append({
            "index": page_index,
            "bounding_box": bounding_box,
            "labels": labels})
        page_index += 1
    fp.close()
    return result


def get_bounding_box(layout):
    bbox = layout.bbox
    bounding_box = {'x0': bbox[0], 'y0': bbox[1], 'x1': bbox[2], 'y1': bbox[3]}
    return bounding_box


def get_text_labels(layout):
    labels = []
    parse_obj(layout._objs, labels)
    return labels


def parse_obj(objs, labels):
    from pdfminer.layout import LTTextLine, LTTextBox, LTFigure, LTImage

    for obj in objs:
        if isinstance(obj, LTTextLine):
            text = obj.get_text().strip()
            if len(text) > 0:
                fontname, fontsize, orientation = get_font(obj)
                add(labels, fontname, fontsize, obj, orientation, text)
        elif isinstance(obj, (LTFigure, LTTextBox)):
            parse_obj(obj._objs, labels)
        elif isinstance(obj, (LTImage)):
            parse_img(obj, labels)

def parse_img(img_obj, labels):
    from pdfminer.image import ImageWriter
    from subprocess import call
    from pdfminer.pdftypes import PDFNotImplementedError
    from os import remove, rename, path

    try:
        logging.info("Writing " + img_obj.name)
        image_writer = ImageWriter(".")
        # TODO this is not thread safe... (so run with "-p 1" for now)
        output_filename = image_writer.export_image(img_obj)
        # TODO rename(output_filename, ...)
        logging.info("Written " + output_filename)
        logging.info("Calling Tesseract hOCR")
        call(["tesseract", output_filename, "out", "-l", "nld", "hocr"])
        # TODO remove(output_filename)

        if path.isfile('./out.html'):
            # TODO fix race condition
            from extracthocr import get_bbox_page, get_bbox_texts
            for label in get_bbox_texts('./out.html'):
                labels.append(convert_label_bbox(label, img_obj.bbox, get_bbox_page('./out.html')))
            remove('./out.html')
        else:
            logging.error("Image object kon niet verwerkt worden door Tesseract: " + output_filename + ".")
    except PDFNotImplementedError as e:
        logging.error("Image object kon niet verwerkt worden: " + str(e) + ". Mogelijk helpt het opslaan vam de PDF met ondersteuning voor Acrobat 4.x en later.")

def convert_label_bbox(label, pdf_coords, img_coords):
    """
    >>> convert_label_bbox({"x0":0,"x1":0,"y0":0,"y1":0},(0,0,1,1),(0,0,1,1))
    {'y1': 0, 'y0': 0, 'x0': 0, 'x1': 0}
    >>> convert_label_bbox({"x0":1,"x1":1,"y0":1,"y1":1},(0,0,1,1),(0,0,1,1))
    {'y1': 1, 'y0': 1, 'x0': 1, 'x1': 1}

    >>> convert_label_bbox({"x0":1,"x1":1,"y0":1,"y1":1},(0,0,2,1),(0,0,1,1))
    {'y1': 1, 'y0': 1, 'x0': 2, 'x1': 2}
    >>> convert_label_bbox({"x0":1,"x1":1,"y0":1,"y1":1},(0,0,1,2),(0,0,1,1))
    {'y1': 2, 'y0': 2, 'x0': 1, 'x1': 1}

    >>> convert_label_bbox({"x0":1,"x1":1,"y0":1,"y1":1},(1,0,2,1),(0,0,1,1))
    {'y1': 1, 'y0': 1, 'x0': 2, 'x1': 2}
    >>> convert_label_bbox({"x0":1,"x1":1,"y0":1,"y1":1},(0,1,1,2),(0,0,1,1))
    {'y1': 2, 'y0': 2, 'x0': 1, 'x1': 1}
    >>> convert_label_bbox({"x0":0.25,"x1":0.75,"y0":0.25,"y1":0.75},(-0.5,20,0.5,21),(0,0,1,1))
    {'y1': 20.75, 'y0': 20.25, 'x0': -0.25, 'x1': 0.25}
    >>> convert_label_bbox({"x0":28,"x1":87,"y0":321,"y1":580},(-0.066051, 256.18399999999997, 1772.045949, 1104.836),(0, 0, 4928, 2360))
    {'y1': 464.75101694915253, 'y0': 371.61505593220335, 'x0': 10.002767181818184, 'x1': 31.219205493506497}
    """
    assert img_coords[0] == 0 and img_coords[1] == 0

    img_width = img_coords[2] - img_coords[0]
    pdf_width = pdf_coords[2] - pdf_coords[0]
    width_scale = pdf_width / img_width
    label['x0'] *= width_scale
    label['x1'] *= width_scale

    img_height = img_coords[3] - img_coords[1]
    pdf_height = pdf_coords[3] - pdf_coords[1]
    height_scale = pdf_height / img_height
    label['y0'] *= height_scale
    label['y1'] *= height_scale

    x_translation = pdf_coords[0] - img_coords[0]
    y_translation = pdf_coords[1] - img_coords[1]

    label['x0'] += x_translation
    label['x1'] += x_translation

    label['y0'] += y_translation
    label['y1'] += y_translation

    return label

def get_font(obj):
    from pdfminer.layout import LTTextLine, LTChar

    for obj in obj._objs:
        if isinstance(obj, LTChar):
            return obj.fontname, obj.size, 'H' if obj.upright else 'V'
        elif isinstance(obj, LTTextLine):
            return get_font(obj)
    return 'unknown', 0, 'H'


def add(labels, fontname, fontsize, obj, orientation, text):
    labels.append({
        "x0": obj.x0,
        "y0": obj.y0,
        "x1": obj.x1,
        "y1": obj.y1,
        "fontname": fontname,
        "fontsize": fontsize,
        "orientation": orientation,
        "text": text})


def write_to_output(filename, labels):
    import json
    import os

    with output_lock:
        if os.path.isfile(filename):
            delim = ','
        else:
            delim = '['
        with open(filename, 'a+') as f:
            f.write(delim)
            f.write(json.dumps(labels, sort_keys=True, indent=4))


def process_queue(queue, filename):
    while True:
        filename_input = queue.get()
        logging.info('Processing %s.', filename_input)
        labels = get_result_from_file(filename_input)
        logging.debug('Writing %s.', filename_input)
        write_to_output(filename, labels)
        logging.debug('File %s is processed.', filename_input)
        queue.task_done()


def process_files():
    import os
    import fnmatch

    file_count = 0
    file_queue = multiprocessing.JoinableQueue()

    if os.path.isfile(filename_output):
        os.remove(filename_output)

    for i in range(max_processes):
        worker = multiprocessing.Process(target=process_queue, args=(file_queue, filename_output))
        worker.daemon = True
        worker.start()

    for root, folder, files in os.walk("."):
        for item in fnmatch.filter(files, filename_filter):
            filename = root + '\\' + item
            logging.debug("Adding %s to the queue.", filename)
            file_count += 1
            file_queue.put(filename)

    file_queue.join()

    with output_lock:
        with open(filename_output, 'a') as f:
            f.write(']')

    logging.info("%d files processed.", file_count)


def show_help():
    print "extractpdf [-h] [-p processes] [-o output] [filter]"
    print "\t-h\tThis helptext."
    print "\t-o\tOutput filename. Defaults to %s." % filename_output
    print "\t-p\tMaximum number of processes. Defaults to %d." % max_processes
    print "\tfilter\tOnly process filenames matching this pattern. Defaults to %s." % filename_filter
    print "\nExample: extractpdf -p 4 -o sample.json 00*.pdf"


if __name__ == '__main__':
    from getopt import getopt, GetoptError
    from sys import argv

    opts, args = [], []
    try:
        opts, args = getopt(argv[1:], "ho:p:")
    except GetoptError:
        print "Incorrect arguments."
        show_help()
        exit(2)
    for opt, arg in opts:
        if opt == "-o":
            filename_output = arg
        if opt == "-p":
            max_processes = int(arg)
        elif opt == "-h":
            show_help()
            exit()
    if len(args) > 0:
        filename_filter = args[0]
    process_files()
