# -*- coding: utf-8 -*-
from odoo import models, api
import logging
import datetime
import os
import pydicom
from pydicom.dataset import FileDataset
from pydicom.uid import generate_uid

_logger = logging.getLogger(__name__)

class OrthancService(models.AbstractModel):
    _name = 'orthanc.service'
    _description = 'Orthanc Integration Service'

    @api.model
    def create_worklist(self, order):
        """
        Generates a DICOM Modality Worklist file for the given order and saves it to the shared directory.
        :param order: orthanc.order record
        """
        _logger.info("Service: Creating Orthanc worklist for Order %s (Study UUID: %s)", order.name, order.study_uuid)

        # Orthanc worklist directory (mounted volume)
        worklist_dir = os.environ.get('ORTHANC_WORKLIST_PATH') or '/opt/bahmni-erp/orthanc/worklists'
        if not os.path.exists(worklist_dir):
            raise Exception(f"Worklist directory {worklist_dir} does not exist. Please check ORTHANC_WORKLIST_PATH setting.")

        # Create DICOM Dataset
        file_meta = pydicom.dataset.FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.31' # Modality Worklist Information Model - FIND SOP Class
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

        ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
        
        # --- Tags Mapping ---
        
        # Specific Character Set
        ds.SpecificCharacterSet = 'ISO_IR 100'

        # Accession Number (Order Number)
        ds.AccessionNumber = order.name[:16] # Truncate to 16 chars

        # Referring Physician
        if order.sale_order_id and order.sale_order_id.provider_id:
            ds.ReferringPhysicianName = order.sale_order_id.provider_id.name
        elif order.sale_order_id and order.sale_order_id.user_id:
            ds.ReferringPhysicianName = order.sale_order_id.user_id.name
        else:
             ds.ReferringPhysicianName = self.env.user.name

        # Patient Information
        patient = order.sale_order_id.partner_id
        if patient:
            # Format: Family^Given^Middle (Odoo uses single Name field, so we just use it)
            ds.PatientName = patient.name
            ds.PatientID = patient.ref or 'UNKNOWN'
            if patient.birthdate:
                ds.PatientBirthDate = patient.birthdate.strftime('%Y%m%d')
            
            if patient.gender:
                if patient.gender == 'male':
                    ds.PatientSex = 'M'
                elif patient.gender == 'female':
                    ds.PatientSex = 'F'
                else:
                    ds.PatientSex = 'O'
            else:
                 ds.PatientSex = 'O' # Default to Other

        # Study Instance UID
        ds.StudyInstanceUID = generate_uid() 

        # Requested Procedure
        term_name = order.product_id.name if order.product_id else 'Radiology Order'
        ds.RequestedProcedureDescription = term_name[:64]
        ds.RequestedProcedureID = f"RP-{order.name}"[:16]
        
        priority_map = {
            'stat': 'STAT',
            'urgent': 'HIGH',
            'scheduled': 'ROUTINE'
        }
        ds.RequestedProcedurePriority = priority_map.get(order.sale_order_id.radiology_priority, 'ROUTINE') 

        # Scheduled Procedure Step Sequence
        sps = pydicom.dataset.Dataset()
        sps.Modality = 'CR' # Could be dynamic
        sps.ScheduledStationAETitle = 'ABERSHUM'
        
        dt_now = datetime.datetime.now()
        sps.ScheduledProcedureStepStartDate = dt_now.strftime('%Y%m%d')
        sps.ScheduledProcedureStepStartTime = dt_now.strftime('%H%M%S')
        sps.ScheduledProcedureStepDescription = term_name[:64]
        sps.ScheduledProcedureStepID = f"SPS-{order.name}"[:16]
        
        ds.ScheduledProcedureStepSequence = pydicom.sequence.Sequence([sps])
        
        # Save File
        safe_name = "".join([c for c in order.name if c.isalnum() or c in ('-','_')]).rstrip()
        filename = f"{safe_name}.wl"
        filepath = os.path.join(worklist_dir, filename)
        
        try:
            ds.save_as(filepath, write_like_original=False)
            _logger.info("Successfully created DICOM worklist file: %s", filepath)
        except Exception as e:
            _logger.error("Failed to write DICOM worklist file: %s", e)
