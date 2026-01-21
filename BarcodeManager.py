from Logger import get_logger
logger = get_logger()

def handleBarcodeInput(barcodeTxt):

    if barcodeTxt == "BC321":
        logger.debug("[DEBUG] routing barcode - BC321 - ")

    else:
        logger.info(f"[INFO] Scanned barcode {barcodeTxt} does not have a function behind it, did you scan the correct barcode?")
    