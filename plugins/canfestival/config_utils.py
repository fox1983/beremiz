#!/usr/bin/env python
# -*- coding: utf-8 -*-

#This file is part of Beremiz, a Integrated Development Environment for
#programming IEC 61131-3 automates supporting plcopen standard and CanFestival. 
#
#Copyright (C) 2007: Edouard TISSERANT and Laurent BESSARD
#
#See COPYING file for copyrights details.
#
#This library is free software; you can redistribute it and/or
#modify it under the terms of the GNU General Public
#License as published by the Free Software Foundation; either
#version 2.1 of the License, or (at your option) any later version.
#
#This library is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#General Public License for more details.
#
#You should have received a copy of the GNU General Public
#License along with this library; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA

from types import *

# Translation between IEC types and Can Open types
IECToCOType = {"BOOL":0x01, "SINT":0x02, "INT":0x03,"DINT":0x04,"LINT":0x10,
               "USINT":0x05,"UINT":0x06,"UDINT":0x07,"ULINT":0x1B,"REAL":0x08,
               "LREAL":0x11,"STRING":0x09,"BYTE":0x05,"WORD":0x06,"DWORD":0x07,
               "LWORD":0x1B,"WSTRING":0x0B}

# Constants for PDO types 
RPDO = 1
TPDO = 2

SlavePDOType = {"I" : TPDO, "Q" : RPDO}
InvertPDOType = {RPDO : TPDO, TPDO : RPDO}

VariableIncrement = 0x100
VariableStartIndex = {TPDO : 0x2000, RPDO : 0x4000}
VariableDirText = {TPDO : "__I", RPDO : "__Q"}
VariableTypeOffset = dict(zip(["","X","B","W","D","L"], range(6)))

TrashVariables = [(1, 0x01), (8, 0x05), (16, 0x06), (32, 0x07), (64, 0x1B)]

def LE_to_BE(value, size):
    """
    Convert Little Endian to Big Endian
    @param value: value expressed in integer
    @param size: number of bytes generated
    @return: a string containing the value converted
    """
    
    data = ("%" + str(size * 2) + "." + str(size * 2) + "X") % value
    list_car = [data[i:i+2] for i in xrange(0, len(data), 2)]
    list_car.reverse()
    return "".join([chr(int(car, 16)) for car in list_car])


def GetNodePDOIndexes(node, type, parameters = False):
    """
    Find the PDO indexes of a node
    @param node: node 
    @param type: type of PDO searched (RPDO or TPDO or both)
    @param parameters: indicate which indexes are expected (PDO paramaters : True or PDO mappings : False)
    @return: a list of indexes found
    """
    
    indexes = []
    if type & RPDO:
        indexes.extend([idx for idx in node.GetIndexes() if 0x1400 <= idx <= 0x15FF])
    if type & TPDO:
        indexes.extend([idx for idx in node.GetIndexes() if 0x1800 <= idx <= 0x19FF])
    if not parameters:
        return [idx + 0x200 for idx in indexes]
    else:
        return indexes


def SearchNodePDOMapping(loc_infos, node):
    """
    Find the PDO indexes of a node
    @param node: node 
    @param type: type of PDO searched (RPDO or TPDO or both)
    @param parameters: indicate which indexes are expected (PDO paramaters : True or PDO mappings : False)
    @return: a list of indexes found
    """
    
    typeinfos = node.GetEntryInfos(loc_infos["type"])
    model = (loc_infos["index"] << 16) + (loc_infos["subindex"] << 8) + typeinfos["size"]
    
    for PDOidx in GetNodePDOIndexes(node, loc_infos["pdotype"]):
        values = node.GetEntry(PDOidx)
        if values != None:
            for subindex, mapping in enumerate(values):
                if subindex != 0 and mapping == model:
                    return PDOidx, subindex
    return None


def GeneratePDOMappingDCF(idx, cobid, transmittype, pdomapping):
    """
    Build concise DCF value for configuring a PDO
    @param idx: index of PDO parameters
    @param cobid: PDO generated COB ID
    @param transmittype : PDO transmit type
    @param pdomapping: list of PDO mappings
    @return: a tuple of value and number of parameters to add to DCF 
    """
    
    # Create entry for RPDO or TPDO parameters and Disable PDO
    dcfdata = LE_to_BE(idx, 2) + LE_to_BE(0x01, 1) + LE_to_BE(0x04, 4) + LE_to_BE((0x80000000 + cobid), 4)
    # Set Transmit type synchrone
    dcfdata += LE_to_BE(idx, 2) + LE_to_BE(0x02, 1) + LE_to_BE(0x01, 4) + LE_to_BE(transmittype, 1)
    # Re-Enable PDO
    #         ---- INDEX -----   --- SUBINDEX ----   ----- SIZE ------   ------ DATA ------
    dcfdata += LE_to_BE(idx, 2) + LE_to_BE(0x01, 1) + LE_to_BE(0x04, 4) + LE_to_BE(0x00000000 + cobid, 4)
    nbparams = 3
    # Map Variables
    for subindex, (name, loc_infos) in enumerate(pdomapping):
        value = (loc_infos["index"] << 16) + (loc_infos["subindex"] << 8) + loc_infos["size"]
        dcfdata += LE_to_BE(idx + 0x200, 2) + LE_to_BE(subindex + 1, 1) + LE_to_BE(0x04, 4) + LE_to_BE(value, 4)
        nbparams += 1
    return dcfdata, nbparams

class ConciseDCFGenerator:

    def __init__(self, nodelist, nodename):
        # Dictionary of location informations classed by name
        self.IECLocations = {}
        # Dictionary of location that have not been mapped yet
        self.LocationsNotMapped = {}
        # Dictionary of location informations classed by name
        self.MasterMapping = {}
        # List of COB IDs available
        self.ListCobIDAvailable = range(0x180, 0x580)
        self.SlavesPdoNumber = {}
        # Dictionary of mapping value where unexpected variables are stored
        self.TrashVariables = {}
        
        self.NodeList = nodelist
        self.Manager = self.NodeList.Manager
        self.MasterNode = self.Manager.GetCurrentNodeCopy()
        self.MasterNode.SetNodeName(nodename)
        self.PrepareMasterNode()

    
    def RemoveUsedNodeCobId(self, node):
        """
        Remove all PDO COB ID used by the given node from the list of available COB ID
        @param node: node
        @return: a tuple of number of RPDO and TPDO for the node
        """
        
        # Get list of all node TPDO and RPDO indexes
        nodeRpdoIndexes = GetNodePDOIndexes(node, RPDO, True)
        nodeTpdoIndexes = GetNodePDOIndexes(node, TPDO, True)
        
        # Mark all the COB ID of the node already mapped PDO as not available
        for PdoIdx in nodeRpdoIndexes + nodeTpdoIndexes:
            pdo_cobid = node.GetEntry(PdoIdx, 0x01)
            # Extract COB ID, if PDO isn't active
            if pdo_cobid > 0x600 :
                pdo_cobid -= 0x80000000
            # Remove COB ID from the list of available COB ID
            if pdo_cobid in self.ListCobIDAvailable:
                self.ListCobIDAvailable.remove(pdo_cobid)
        
        return len(nodeRpdoIndexes), len(nodeTpdoIndexes)

    
    def PrepareMasterNode(self):
        """
        Add mandatory entries for DCF generation into MasterNode.
        """
        
        # Adding DCF entry into Master node
        if not self.MasterNode.IsEntry(0x1F22):
            self.MasterNode.AddEntry(0x1F22, 1, "")
        self.Manager.AddSubentriesToCurrent(0x1F22, 127, self.MasterNode)
        
        # Adding trash mappable variables for unused mapped datas
        idxTrashVariables = 0x2000 + self.MasterNode.GetNodeID()
        # Add an entry for storing unexpected all variable
        self.Manager.AddMapVariableToCurrent(idxTrashVariables, self.MasterNode.GetNodeName()+"_trashvariables", 3, len(TrashVariables), self.MasterNode)
        for subidx, (size, typeidx) in enumerate(TrashVariables):
            # Add a subentry for storing unexpected variable of this size
            self.Manager.SetCurrentEntry(idxTrashVariables, subidx + 1, "TRASH%d" % size, "name", None, self.MasterNode)
            self.Manager.SetCurrentEntry(idxTrashVariables, subidx + 1, typeidx, "type", None, self.MasterNode)
            # Store the mapping value for this entry
            self.TrashVariables[size] = (idxTrashVariables << 16) + ((subidx + 1) << 8) + size
        
        RPDOnumber, TPDOnumber = self.RemoveUsedNodeCobId(self.MasterNode)
        
        # Store the indexes of the first RPDO and TPDO available for MasterNode
        self.CurrentPDOParamsIdx = {RPDO : 0x1400 + RPDOnumber, TPDO : 0x1800 + TPDOnumber}

        # Prepare MasterNode with all nodelist slaves
        for idx, (nodeid, nodeinfos) in enumerate(self.NodeList.SlaveNodes.items()):
            node = nodeinfos["Node"]
            node.SetNodeID(nodeid)
            
            RPDOnumber, TPDOnumber = self.RemoveUsedNodeCobId(node)
            
            # Store the number of TPDO and RPDO for this node
            self.SlavesPdoNumber[nodeid] = {RPDO : RPDOnumber, TPDO : TPDOnumber}
            
            # Get Slave's default SDO server parameters
            RSDO_cobid = node.GetEntry(0x1200,0x01)
            if not RSDO_cobid:
                RSDO_cobid = 0x600 + nodeid
            TSDO_cobid = node.GetEntry(0x1200,0x02)
            if not TSDO_cobid:
                TSDO_cobid = 0x580 + nodeid
            
            # Configure Master's SDO parameters entries
            self.Manager.ManageEntriesOfCurrent([0x1280 + idx], [], self.MasterNode)
            self.MasterNode.SetEntry(0x1280 + idx, 0x01, RSDO_cobid)
            self.MasterNode.SetEntry(0x1280 + idx, 0x02, TSDO_cobid)
            self.MasterNode.SetEntry(0x1280 + idx, 0x03, nodeid)        
        
    
    def GetMasterNode(self):
        """
        Return MasterNode.
        """
        return self.MasterNode

    
    def GetNewCobID(self, nodeid, type):
        """
        Select a COB ID from the list of those available
        @param nodeid: id of the slave (int)
        @param type: type of PDO (RPDO or TPDO)
        @return: a tuple of the COD ID and PDO index or None
        """
        # Verify that there is still some cobid available
        if len(self.ListCobIDAvailable) == 0:
            return None
        
        # Get the number of PDO of the type given for the node
        nbSlavePDO = self.SlavesPdoNumber[nodeid][type]
        if type == RPDO:
            if nbSlavePDO < 4:
                # For the four first RPDO -> cobid = 0x200 + ( numPdo parameters * 0x100) + nodeid
                newcobid = (0x200 + nbSlavePDO * 0x100 + nodeid)
                # Return calculated cobid if it's still available
                if newcobid in self.ListCobIDAvailable:
                    self.ListCobIDAvailable.remove(newcobid)
                    return newcobid, 0x1400 + nbSlavePDO
            # Return the first cobid available if no cobid found
            return self.ListCobIDAvailable.pop(0), 0x1400 + nbSlavePDO
    
        elif type == TPDO:
            if nbSlavePDO < 4:
                # For the four first TPDO -> cobid = 0x180 + ( numPdo parameters * 0x100) + nodeid
                newcobid = (0x180 + nbSlavePDO * 0x100 + nodeid)
                # Return calculated cobid if it's still available
                if newcobid in self.ListCobIDAvailable:
                    self.ListCobIDAvailable.remove(newcobid)
                    return newcobid, 0x1800 + nbSlavePDO
            # Return the first cobid available if no cobid found
            return self.ListCobIDAvailable.pop(0), 0x1800 + nbSlavePDO
        
        return None
    
    
    def AddParamsToDCF(self, nodeid, data, nbparams):
        """
        Select a COB ID from the list of those available
        @param nodeid: id of the slave (int)
        @param data: data to add to slave DCF (string)
        @param nbparams: number of params added to slave DCF (int)
        """
        # Get current DCF for slave
        nodeDCF = self.MasterNode.GetEntry(0x1F22, nodeid)
        
        # Extract data and number of params in current DCF
        if nodeDCF != None and nodeDCF != '':
            tmpnbparams = [i for i in nodeDCF[:4]]
            tmpnbparams.reverse()
            nbparams += int(''.join(["%2.2x"%ord(i) for i in tmpnbparams]), 16)
            data = nodeDCF[4:] + data
        
        # Build new DCF
        dcf = LE_to_BE(nbparams, 0x04) + data
        # Set new DCF for slave
        self.MasterNode.SetEntry(0x1F22, nodeid, dcf)
    
    def AddPDOMapping(self, nodeid, pdotype, pdomapping, sync_TPDOs):
        """
        Select a COB ID from the list of those available
        @param nodeid: id of the slave (int)
        @param pdotype: type of PDO to generated (RPDO or TPDO)
        @param pdomapping: list od variables to map with PDO
        """
        # Get a new cob id
        result = self.GetNewCobID(nodeid, pdotype)
        if result:
            new_cobid, new_idx = result
            
            # Increment the number of PDO of this type for node
            self.SlavesPdoNumber[nodeid][pdotype] += 1
            
            # Add an entry to MasterMapping
            self.MasterMapping[new_cobid] = {"type" : InvertPDOType[pdotype], 
                "mapping" : [None] + [(loc_infos["type"], name) for name, loc_infos in pdomapping]}
            
            # Return the data to add to DCF
            if sync_TPDOs:
                return GeneratePDOMappingDCF(new_idx, new_cobid, 0x01, pdomapping)
            else:
                return GeneratePDOMappingDCF(new_idx, new_cobid, 0xFF, pdomapping)
        return 0, ""
    
    def GenerateDCF(self, locations, current_location, sync_TPDOs):
        """
        Generate Concise DCF of MasterNode for the locations list given
        @param locations: list of locations to be mapped
        @param current_location: tuple of the located prefixes not to be considered
        @param sync_TPDOs: indicate if TPDO must be synchronous
        """
        
        #-------------------------------------------------------------------------------
        #               Verify that locations correspond to real slave variables
        #-------------------------------------------------------------------------------
        
        # Get list of locations check if exists and mappables -> put them in IECLocations
        for location in locations:
            COlocationtype = IECToCOType[location["IEC_TYPE"]]
            name = location["NAME"]
            if name in self.IECLocations:
                if self.IECLocations[name]["type"] != COlocationtype:
                    raise ValueError, "Conflict type for location \"%s\"" % name 
            else:
                # Get only the part of the location that concern this node
                loc = location["LOC"][len(current_location):]
                # loc correspond to (ID, INDEX, SUBINDEX [,BIT])
                if len(loc) not in (3, 4):
                    raise ValueError, "Bad location size : %s"%str(loc)
                
                direction = location["DIR"]
                
                sizelocation = location["SIZE"]
                
                # Extract and check nodeid
                nodeid, index, subindex = loc[:3]
                
                # Check Id is in slave node list
                if nodeid not in self.NodeList.SlaveNodes.keys():
                    raise ValueError, "Non existing node ID : %d (variable %s)" % (nodeid,name)
                
                # Get the model for this node (made from EDS)
                node = self.NodeList.SlaveNodes[nodeid]["Node"]
                
                # Extract and check index and subindex
                if not node.IsEntry(index, subindex):
                    raise ValueError, "No such index/subindex (%x,%x) in ID : %d (variable %s)" % (index,subindex,nodeid,name)
                
                # Get the entry info
                subentry_infos = node.GetSubentryInfos(index, subindex)
                
                # If a PDO mappable
                if subentry_infos and subentry_infos["pdo"]:
                    if sizelocation == "X" and len(loc) > 3:
                        numbit = loc[4]
                    elif sizelocation != "X" and len(loc) > 3:
                        raise ValueError, "Cannot set bit offset for non bool '%s' variable (ID:%d,Idx:%x,sIdx:%x))" % (name,nodeid,index,subindex)
                    else:
                        numbit = None
                    
                    entryinfos = node.GetSubentryInfos(index, subindex)
                    if entryinfos["type"] != COlocationtype:
                        raise ValueError, "Invalid type \"%s\"-> %d != %d  for location\"%s\"" % (location["IEC_TYPE"], COlocationtype, entryinfos["type"] , name)
                    
                    typeinfos = node.GetEntryInfos(COlocationtype)
                    self.IECLocations[name] = {"type":COlocationtype, "pdotype":SlavePDOType[direction],
                                                "nodeid": nodeid, "index": index,"subindex": subindex,
                                                "bit": numbit, "size": typeinfos["size"], "sizelocation": sizelocation}
                else:
                    raise ValueError, "Not PDO mappable variable : '%s' (ID:%d,Idx:%x,sIdx:%x))" % (name,nodeid,index,subindex)
        
        #-------------------------------------------------------------------------------
        #                         Search for locations already mapped
        #-------------------------------------------------------------------------------
        
        for name, locationinfos in self.IECLocations.items():
            node = self.NodeList.SlaveNodes[locationinfos["nodeid"]]["Node"]
            
            # Search if slave has a PDO mapping this locations
            result = SearchNodePDOMapping(locationinfos, node)
            if result != None:
                index, subindex = result
                # Get COB ID of the PDO
                cobid = self.NodeList.GetSlaveNodeEntry(locationinfos["nodeid"], index - 0x200, 1)
                
                # Verify that PDO transmit type is conform to sync_TPDOs
                transmittype = self.NodeList.GetSlaveNodeEntry(locationinfos["nodeid"], index - 0x200, 2)
                if sync_TPDOs and transmittype != 0x01 or transmittype != 0xFF:
                    if sync_TPDOs:
                        # Change TransmitType to SYNCHRONE
                        data, nbparams = GeneratePDOMappingDCF(index - 0x200, cobid, 0x01, [])
                    else:
                        # Change TransmitType to ASYCHRONE
                        data, nbparams = GeneratePDOMappingDCF(index - 0x200, cobid, 0xFF, [])
                    
                    # Add entry to slave dcf to change transmit type of 
                    self.AddParamsToDCF(locationinfos["nodeid"], data, nbparams)
                
                # Add PDO to MasterMapping
                if cobid not in self.MasterMapping.keys():
                    mapping = [None]
                    values = node.GetEntry(index)
                    # Store the size of each entry mapped in PDO
                    for value in values[1:]:
                        mapping.append(value % 0x100)
                    self.MasterMapping[cobid] = {"type" : InvertPDOType[locationinfos["pdotype"]], "mapping" : mapping}
            
                # Indicate that this PDO entry must be saved
                self.MasterMapping[cobid]["mapping"][subindex] = (locationinfos["type"], name)
                
            else:
                # Add location to those that haven't been mapped yet
                if locationinfos["nodeid"] not in self.LocationsNotMapped.keys():
                    self.LocationsNotMapped[locationinfos["nodeid"]] = {TPDO : [], RPDO : []}
                self.LocationsNotMapped[locationinfos["nodeid"]][locationinfos["pdotype"]].append((name, locationinfos))
    
        #-------------------------------------------------------------------------------
        #                         Build concise DCF for the others locations
        #-------------------------------------------------------------------------------
        
        for nodeid, locations in self.LocationsNotMapped.items():
            node = nodelist.SlaveNodes[nodeid]["Node"]
            
            # Initialize number of params and data to add to node DCF
            nbparams = 0
            dataparams = ""
            
            # Generate the best PDO mapping for each type of PDO
            for pdotype in (TPDO, RPDO):
                pdosize = 0
                pdomapping = []
                for name, loc_infos in locations[pdotype]:
                    pdosize += loc_infos["size"]
                    # If pdo's size > 64 bits
                    if pdosize > 64:
                        # Generate a new PDO Mapping
                        data, nbaddedparams = self.AddPDOMapping(nodeid, pdotype, pdomapping, sync_TPDOs)
                        dataparams += data
                        nbparams += nbaddedparams
                        pdosize = loc_infos["size"]
                        pdomapping = [(name, loc_infos)]
                    else:
                        pdomapping.append((name, loc_infos))
                # If there isn't locations yet but there is still a PDO to generate
                if len(pdomapping) > 0:
                    # Generate a new PDO Mapping
                    data, nbaddedparams = self.AddPDOMapping(nodeid, pdotype, pdomapping, sync_TPDOs)
                    dataparams += data
                    nbparams += nbaddedparams
            
            # Add number of params and data to node DCF
            self.AddParamsToDCF(nodeid, dataparams, nbparams)
        
        #-------------------------------------------------------------------------------
        #                         Master Node Configuration
        #-------------------------------------------------------------------------------
        
        # Generate Master's Configuration from informations stored in MasterMapping
        for cobid, pdo_infos in self.MasterMapping.items():
            # Get next PDO index in MasterNode for this PDO type
            current_idx = self.CurrentPDOParamsIdx[pdo_infos["type"]]
            
            # Search if there is already a PDO in MasterNode with this cob id
            for idx in GetNodePDOIndexes(self.MasterNode, pdo_infos["type"], True):
                if self.MasterNode.GetEntry(idx, 1) == cobid:
                    current_idx = idx
            
            # Add a PDO to MasterNode if not PDO have been found
            if current_idx == self.CurrentPDOParamsIdx[pdo_infos["type"]]:
                addinglist = [current_idx, current_idx + 0x200]
                self.Manager.ManageEntriesOfCurrent(addinglist, [], self.MasterNode)
                self.MasterNode.SetEntry(current_idx, 0x01, cobid)
                
                # Increment the number of PDO for this PDO type
                self.CurrentPDOParamsIdx[pdo_infos["type"]] += 1
            
            # Change the transmit type of the PDO
            if sync_TPDOs:
                self.MasterNode.SetEntry(current_idx, 0x02, 0x01)
            else:
                self.MasterNode.SetEntry(current_idx, 0x02, 0xFF)
            
            # Add some subentries to PDO mapping if there is not enough
            if len(pdo_infos["mapping"]) > 1:
                self.Manager.AddSubentriesToCurrent(current_idx + 0x200, len(pdo_infos["mapping"]) - 1, self.MasterNode)
            
            # Generate MasterNode's PDO mapping
            for subindex, variable in enumerate(pdo_infos["mapping"]):
                if subindex == 0:
                    continue
                new_index = False
                
                if type(variable) == IntType:
                    # If variable is an integer then variable is unexpected
                    self.MasterNode.SetEntry(current_idx + 0x200, subindex, self.TrashVariables[variable])
                else:
                    typeidx, varname = variable
                    variable_infos = self.IECLocations[varname]
                    
                    # Calculate base index for storing variable
                    mapvariableidx = VariableStartIndex[variable_infos["pdotype"]] + \
                                     VariableTypeOffset[variable_infos["sizelocation"]] * VariableIncrement + \
                                     variable_infos["nodeid"]
                    
                    # Search for an entry that has an empty subindex 
                    while mapvariableidx < VariableStartIndex[variable_infos["pdotype"]] + 0x2000:
                        # Entry doesn't exist
                        if not self.MasterNode.IsEntry(mapvariableidx):    
                            # Generate entry name
                            indexname = "%s%s%s_%d"%(VariableDirText[variable_infos["pdotype"]],
                                                     variable_infos["sizelocation"],
                                                     '_'.join(map(str,current_location)),
                                                     variable_infos["nodeid"])
                            # Add entry to MasterNode
                            self.Manager.AddMapVariableToCurrent(mapvariableidx, indexname, 3, 1, self.MasterNode)
                            new_index = True
                            nbsubentries = self.MasterNode.GetEntry(mapvariableidx, 0x00)
                        else:
                            # Get Number of subentries already defined
                            nbsubentries = self.MasterNode.GetEntry(mapvariableidx, 0x00)
                            # if entry is full, go to next entry possible or stop now
                            if nbsubentries == 0xFF:
                                mapvariableidx += 8 * VariableIncrement
                            else:
                                break
                                
                    # Verify that a not full entry has been found
                    if mapvariableidx < VariableStartIndex[variable_infos["pdotype"]] + 0x2000:
                        # Generate subentry name
                        if variable_infos["bit"] != None:
                            subindexname = "%(index)d_%(subindex)d_%(bit)d"%variable_infos
                        else:
                            subindexname = "%(index)d_%(subindex)d"%variable_infos
                        # If entry have just been created, no subentry have to be added
                        if not new_index:
                            self.Manager.AddSubentriesToCurrent(mapvariableidx, 1, self.MasterNode)
                            nbsubentries += 1
                        # Add informations to the new subentry created
                        self.MasterNode.SetMappingEntry(mapvariableidx, nbsubentries, values = {"name" : subindexname})
                        self.MasterNode.SetMappingEntry(mapvariableidx, nbsubentries, values = {"type" : typeidx})
                        
                        # Set value of the PDO mapping
                        typeinfos = self.Manager.GetEntryInfos(typeidx)
                        if typeinfos != None:
                            value = (mapvariableidx << 16) + ((nbsubentries) << 8) + typeinfos["size"]
                            self.MasterNode.SetEntry(current_idx + 0x200, subindex, value)

def GenerateConciseDCF(locations, current_location, nodelist, sync_TPDOs, nodename):
    """
    Fills a CanFestival network editor model, with DCF with requested PDO mappings.
    @param locations: List of complete variables locations \
        [{"IEC_TYPE" : the IEC type (i.e. "INT", "STRING", ...)
        "NAME" : name of the variable (generally "__IW0_1_2" style)
        "DIR" : direction "Q","I" or "M"
        "SIZE" : size "X", "B", "W", "D", "L"
        "LOC" : tuple of interger for IEC location (0,1,2,...)
        }, ...]
    @param nodelist: CanFestival network editor model
    @return: a modified copy of the given CanFestival network editor model
    """
    
    dcfgenerator = ConciseDCFGenerator(nodelist, nodename)
    dcfgenerator.GenerateDCF(locations, current_location, sync_TPDOs)
    return dcfgenerator.GetMasterNode()

if __name__ == "__main__":
    import os, sys, getopt

    def usage():
        print """
Usage of config_utils.py test :

    %s [options]

Options:
    --help  (-h)
            Displays help informations for config_utils

    --reset (-r)
            Reset the reference result of config_utils test.
            Use with caution. Be sure that config_utils
            is currently working properly.
"""%sys.argv[0]
    
    # Boolean that indicate if reference result must be redefined
    reset = False

    # Extract command options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hr", ["help","reset"])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)

    # Test each option
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-r", "--reset"):
            reset = True

    # Extract workspace base folder
    base_folder = sys.path[0]
    for i in xrange(3):
        base_folder = os.path.split(base_folder)[0]
    # Add CanFestival folder to search pathes
    sys.path.append(os.path.join(base_folder, "CanFestival-3", "objdictgen"))
    
    from nodemanager import *
    from nodelist import *
    
    # Open the test nodelist contained into test_config folder
    manager = NodeManager()
    nodelist = NodeList(manager)
    result = nodelist.LoadProject("test_config")
    
    # List of locations, we try to map for test
    locations = [{"IEC_TYPE":"BYTE","NAME":"__IB0_1_64_24576_1","DIR":"I","SIZE":"B","LOC":(0,1,64,24576,1)},
                 {"IEC_TYPE":"INT","NAME":"__IW0_1_64_25601_2","DIR":"I","SIZE":"W","LOC":(0,1,64,25601,2)},
                 {"IEC_TYPE":"INT","NAME":"__IW0_1_64_25601_3","DIR":"I","SIZE":"W","LOC":(0,1,64,25601,3)},
                 {"IEC_TYPE":"INT","NAME":"__QW0_1_64_25617_2","DIR":"Q","SIZE":"W","LOC":(0,1,64,25617,1)},
                 {"IEC_TYPE":"BYTE","NAME":"__IB0_1_64_24578_1","DIR":"I","SIZE":"B","LOC":(0,1,64,24578,1)},
                 {"IEC_TYPE":"UDINT","NAME":"__ID0_1_64_25638_1","DIR":"I","SIZE":"D","LOC":(0,1,64,25638,1)},
                 {"IEC_TYPE":"UDINT","NAME":"__ID0_1_64_25638_2","DIR":"I","SIZE":"D","LOC":(0,1,64,25638,2)},
                 {"IEC_TYPE":"UDINT","NAME":"__ID0_1_64_25638_3","DIR":"I","SIZE":"D","LOC":(0,1,64,25638,3)},
                 {"IEC_TYPE":"UDINT","NAME":"__ID0_1_64_25638_4","DIR":"I","SIZE":"D","LOC":(0,1,64,25638,4)}]
    
    # Generate MasterNode configuration
    try:
        masternode = GenerateConciseDCF(locations, (0, 1), nodelist, True)
    except ValueError, message:
        print "%s\nTest Failed!"%message
        sys.exit()
    
    # Get Text corresponding to MasterNode 
    result = masternode.PrintString()
    
    # If reset has been choosen
    if reset:
        # Write Text into reference result file
        file = open("test_config/result.txt", "w")
        file.write(result)
        file.close()
        
        print "Reset Successful!"
    else:
        # Test each line of the result with the reference result
        test = [line.rstrip() for line in result.splitlines()]
        
        file = open("test_config/result.txt", "r")
        model = [line.rstrip() for line in file.readlines() if line.rstrip()]
        file.close()
        
        errors = 0
        for i, line in enumerate(model):
            if i >= len(test):
                errors += 1
                print "Line %d disappear :\n%s\n"%(i + 1, line)
            elif line != test[i]:
                errors += 1
                print "Error on line %d :\n%s\nInstead of :\n%s\n"%(i + 1, test[i], line)
        for i in xrange(len(model), len(test)):
            errors += 1
            print "Line %d appear :\n%s\n"%(i + 1, test[i])
        
        if errors > 0:
            print "%d errors found.\nTest Failed!"%errors
        else:
            print "Test Successful!"
