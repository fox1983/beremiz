
import wx

from subindextable import EditingPanel
from networkedit import NetworkEditorTemplate
from controls import EditorPanel

[ID_NETWORKEDITOR, 
] = [wx.NewId() for _init_ctrls in range(1)]

[ID_NETWORKEDITORCONFNODEMENUADDSLAVE, ID_NETWORKEDITORCONFNODEMENUREMOVESLAVE, 
 ID_NETWORKEDITORCONFNODEMENUMASTER, 
] = [wx.NewId() for _init_coll_ConfNodeMenu_Items in range(3)]

[ID_NETWORKEDITORMASTERMENUNODEINFOS, ID_NETWORKEDITORMASTERMENUDS301PROFILE,
 ID_NETWORKEDITORMASTERMENUDS302PROFILE, ID_NETWORKEDITORMASTERMENUDSOTHERPROFILE,
 ID_NETWORKEDITORMASTERMENUADD, 
] = [wx.NewId() for _init_coll_MasterMenu_Items in range(5)]

[ID_NETWORKEDITORADDMENUSDOSERVER, ID_NETWORKEDITORADDMENUSDOCLIENT,
 ID_NETWORKEDITORADDMENUPDOTRANSMIT, ID_NETWORKEDITORADDMENUPDORECEIVE,
 ID_NETWORKEDITORADDMENUMAPVARIABLE, ID_NETWORKEDITORADDMENUUSERTYPE,
] = [wx.NewId() for _init_coll_AddMenu_Items in range(6)]

class NetworkEditor(EditorPanel, NetworkEditorTemplate):
    
    ID = ID_NETWORKEDITOR
    
    def _init_coll_MainSizer_Items(self, parent):
        parent.AddWindow(self.NetworkNodes, 0, border=5, flag=wx.GROW|wx.ALL)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)
    
    def _init_sizers(self):
        self.MainSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=1, vgap=0)
        
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)
        
        self.Editor.SetSizer(self.MainSizer)
    
    def _init_Editor(self, prnt):
        self.Editor = wx.Panel(id=-1, parent=prnt, pos=wx.Point(0, 0), 
                size=wx.Size(0, 0), style=wx.TAB_TRAVERSAL)
        
        NetworkEditorTemplate._init_ctrls(self, self.Editor)
        
        self._init_sizers()
        
    def __init__(self, parent, controler, window):
        EditorPanel.__init__(self, parent, "", window, controler)
        NetworkEditorTemplate.__init__(self, controler, window, False)
    
        img = wx.Bitmap(controler.GetIconPath(), wx.BITMAP_TYPE_PNG).ConvertToImage()
        self.SetIcon(wx.BitmapFromImage(img.Rescale(16, 16)))
        
        self.RefreshNetworkNodes()
        self.RefreshBufferState()
    
    def __del__(self):
        self.Controler.OnCloseEditor(self)
    
    def GetConfNodeMenuItems(self):
        add_menu = [(wx.ITEM_NORMAL, (_('SDO Server'), ID_NETWORKEDITORADDMENUSDOSERVER, '', self.OnAddSDOServerMenu)),
                    (wx.ITEM_NORMAL, (_('SDO Client'), ID_NETWORKEDITORADDMENUSDOCLIENT, '', self.OnAddSDOClientMenu)),
                    (wx.ITEM_NORMAL, (_('PDO Transmit'), ID_NETWORKEDITORADDMENUPDOTRANSMIT, '', self.OnAddPDOTransmitMenu)),
                    (wx.ITEM_NORMAL, (_('PDO Receive'), ID_NETWORKEDITORADDMENUPDORECEIVE, '', self.OnAddPDOReceiveMenu)),
                    (wx.ITEM_NORMAL, (_('Map Variable'), ID_NETWORKEDITORADDMENUMAPVARIABLE, '', self.OnAddMapVariableMenu)),
                    (wx.ITEM_NORMAL, (_('User Type'), ID_NETWORKEDITORADDMENUUSERTYPE, '', self.OnAddUserTypeMenu))]
        
        profile = self.Manager.GetCurrentProfileName()
        if profile not in ("None", "DS-301"):
            other_profile_text = _("%s Profile") % profile
            add_menu.append((wx.ITEM_SEPARATOR, None))
            for text, indexes in self.Manager.GetCurrentSpecificMenu():
                add_menu.append((wx.ITEM_NORMAL, (text, wx.NewId(), '', self.GetProfileCallBack(text))))
        else:
            other_profile_text = _('Other Profile')
        
        master_menu = [(wx.ITEM_NORMAL, (_('Node infos'), ID_NETWORKEDITORMASTERMENUNODEINFOS, '', self.OnNodeInfosMenu)),
                       (wx.ITEM_NORMAL, (_('DS-301 Profile'), ID_NETWORKEDITORMASTERMENUDS301PROFILE, '', self.OnCommunicationMenu)),
                       (wx.ITEM_NORMAL, (_('DS-302 Profile'), ID_NETWORKEDITORMASTERMENUDS302PROFILE, '', self.OnOtherCommunicationMenu)),
                       (wx.ITEM_NORMAL, (other_profile_text, ID_NETWORKEDITORMASTERMENUDSOTHERPROFILE, '', self.OnEditProfileMenu)),
                       (wx.ITEM_SEPARATOR, None),
                       (add_menu, (_('Add'), ID_NETWORKEDITORMASTERMENUADD))]
        
        return [(wx.ITEM_NORMAL, (_('Add slave'), ID_NETWORKEDITORCONFNODEMENUADDSLAVE, '', self.OnAddSlaveMenu)),
                (wx.ITEM_NORMAL, (_('Remove slave'), ID_NETWORKEDITORCONFNODEMENUREMOVESLAVE, '', self.OnRemoveSlaveMenu)),
                (wx.ITEM_SEPARATOR, None),
                (master_menu, (_('Master'), ID_NETWORKEDITORCONFNODEMENUMASTER))]
    
    def RefreshMainMenu(self):
        pass
    
    def RefreshConfNodeMenu(self, confnode_menu):
        confnode_menu.Enable(ID_NETWORKEDITORCONFNODEMENUMASTER, self.NetworkNodes.GetSelection() == 0)
    
    def GetTitle(self):
        fullname = self.Controler.CTNFullName()
        if not self.Manager.CurrentIsSaved():
            return "~%s~" % fullname
        return fullname

    def RefreshView(self):
        self.RefreshCurrentIndexList()
    
    def RefreshBufferState(self):
        NetworkEditorTemplate.RefreshBufferState(self)
        self.ParentWindow.RefreshTitle()
        self.ParentWindow.RefreshFileMenu()
        self.ParentWindow.RefreshEditMenu()
        self.ParentWindow.RefreshPageTitles()
    
    def OnNodeSelectedChanged(self, event):
        NetworkEditorTemplate.OnNodeSelectedChanged(self, event)
        wx.CallAfter(self.ParentWindow.RefreshConfNodeMenu)
        
