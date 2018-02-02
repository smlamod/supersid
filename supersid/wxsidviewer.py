"""
wxSidViewer class implements a graphical user interface for SID based on wxPython

About Threads and wxPython http://www.blog.pythonlibrary.org/2010/05/22/wxpython-and-threads/

Each Viewer must implement:
- __init__(): all initializations
- run(): main loop to get user input
- close(): cleaning up
- status_display(): display a message in a status bar or equivalent
"""
from __future__ import print_function

import matplotlib
matplotlib.use('WXAgg') # select back-end before pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
import wx
import wx.lib.agw.aui as Aui
from wx.lib.pubsub import setupkwargs
from wx.lib.pubsub import pub as Publisher

import supersid_plot as SSP
from config import FILTERED, RAW, CALL_SIGN, FREQUENCY #A added CALL_SIGN and FREQUENCY

class wxSidViewer(wx.Frame):
    '''                  
    Frame, Menu, Panel, BoxSizer are wx things and FigureCanvas, Figure, Axes are MPL things
    Viewer =>> Panel =>> FigureCanvas =>> Figure => Axes
    frame close events are forwarded to SuperSID class
    '''

    def __init__(self, controller):
        """SuperSID Viewer using wxPython GUI for standalone and client.
        Creation of the Frame with menu and graph display using matplotlib
        """
        matplotlib.use('WXAgg') # select back-end before pylab
        # the application MUST created first
        #S causes the first error
        self.app = wx.App(redirect=False)
        #
        self.version = "1.3.1 20150421 (wx)"
        self.controller = controller  # previously referred as 'parent'      
        # Frame
        wx.Frame.__init__(self, None, -1, "supersid @ " + self.controller.config['site_name'], pos = (20, 20), size=(1000,400))     
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Icon
        try: 
            self.SetIcon(wx.Icon("supersid_icon.png", wx.BITMAP_TYPE_PNG))
        finally:
            pass

        # All Menus creation
        menu_item_file = wx.Menu()
        save_buffers_menu = menu_item_file.Append(wx.NewId(), '&Save Raw Buffers\tCtrl+B', 'Save Raw Buffers')
        save_filtered_menu = menu_item_file.Append(wx.NewId(),'&Save Filtered Buffers\tCtrl+F', 'Save Filtered Buffers')
        exit_menu = menu_item_file.Append(wx.NewId(), '&Quit\tCtrl+Q', 'Quit Super SID')
        qdc_menu = menu_item_file.Append(wx.NewId(), '&Create QDC', 'Create QDC file') # @a

        menu_item_plot = wx.Menu()
        plot_menu = menu_item_plot.Append(wx.NewId(), '&Plot\tCtrl+P', 'Plot data')

        menu_item_help = wx.Menu()
        about_menu = menu_item_help.Append(wx.NewId(), '&About', 'About Super SID')

        menubar = wx.MenuBar()
        menubar.Append(menu_item_file, '&File')
        menubar.Append(menu_item_plot, '&Plot')
        menubar.Append(menu_item_help, '&Help')
        
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.on_save_buffers, save_buffers_menu)
        self.Bind(wx.EVT_MENU, self.on_save_filtered, save_filtered_menu)
        self.Bind(wx.EVT_MENU, self.on_plot, plot_menu)
        self.Bind(wx.EVT_MENU, self.on_about, about_menu)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_menu)
        self.Bind(wx.EVT_MENU, self.on_qdc,qdc_menu) # @a

        # Frame 
        frameSizer = wx.BoxSizer(wx.VERTICAL)
        
        #frameSizer.SetSizer(frameSizer)
     
               
        # @a Combobox for Station Selection
        self.label = wx.StaticText(self, label="Stations") #, style=wx.ALIGN_CENTER)
        frameSizer.Add(self.label, 0, wx.ALL, 5)
        selection = self.controller.logger.sid_file.stations
        #selection = map(str, self.controller.config['call_sign'].split(','))
        #stationselect = ["NWC","JJI","VTX4", "VTX1", "FTA", "NML"] 
        self.combobox = wx.ComboBox(self, choices=selection, style=wx.CB_READONLY)
        frameSizer.Add(self.combobox, 0, wx.ALL, 5)

        #frameSizer.AddStretchSpacer()
        self.combobox.Bind(wx.EVT_COMBOBOX, self.OnCombo)

        #self.Center(wx.BOTH)
       # self.Show()

        
        # @a auinotebook 012518       
        nbstyle = Aui.AUI_NB_DEFAULT_STYLE
        nbstyle &= ~(Aui.AUI_NB_CLOSE_ON_ACTIVE_TAB)
        auiNotebook = Aui.AuiNotebook(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, agwStyle=nbstyle)
        
        # @a Add 2 pages to the wxAuinotebook widget
        # @a First Page
        tab_psd_panel = wx.Panel(auiNotebook)    
        tab_psd_panel.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_INFOBK))
        auiNotebook.AddPage(tab_psd_panel, "Spectrum", True, wx.NullBitmap)
        psd_sizer = wx.BoxSizer(wx.VERTICAL)
        tab_psd_panel.SetSizer(psd_sizer) 

        # @a for debugging purposes
        #statictext = wx.StaticText(tab_psd_panel, label="This tab shows the psd graph")
        #psd_sizer.Add(statictext, 0, wx.ALL, 5)

        # @a Second Page
        tab_Rtsid = wx.Panel(auiNotebook)
        tab_Rtsid.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_INFOBK))
        auiNotebook.AddPage(tab_Rtsid, "Realtime SID", False, wx.NullBitmap)
        rtsid_sizer = wx.BoxSizer(wx.VERTICAL)
        tab_Rtsid.SetSizer(rtsid_sizer)

        
        # @a Add the notebook in frameSizer      
        frameSizer.Add(auiNotebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(frameSizer)
        self.Layout()
        self.Centre(wx.BOTH)
        
        # @a changes below to accomodate for variables psd_panel -> tab_psd_panel 01252018

        ## FigureCanvas for Spectrum Page    
        psd_figure = Figure(facecolor='beige') # 'bisque' 'antiquewhite' 'FFE4C4' 'F5F5DC' 'grey'
        psd_axes = psd_figure.add_subplot(111)

        self.canvas = FigureCanvas(tab_psd_panel, -1, psd_figure)
        self.canvas.mpl_connect('button_press_event', self.on_click) # MPL call back
        # @a to hide canvas
        # @a self.canvas.Show(False)

        psd_sizer.Add(self.canvas, 1, wx.EXPAND)       
        self.axes = psd_figure.add_subplot(111)
        self.axes.hold(False)
        
        ## FigureCanvas for RealTime SID page
        rtsid_figure = Figure(facecolor='beige')
        rtsid_axes = rtsid_figure.add_subplot(111)

        self.canvas2 = FigureCanvas(tab_Rtsid, -1, rtsid_figure)
        self.canvas2.mpl_connect('button_press_event', self.on_click) # MPL call back

        rtsid_sizer.Add(self.canvas2, 1, wx.EXPAND)
        # figure for realtimeplots
        #self.axes = rtsid_figure.add_subplot(111)
        #self.axes.hold(False)

        # StatusBar
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetFieldsCount(2)
        
        # Default View
        self.SetMinSize((600,600))
        psd_sizer.SetItemMinSize(tab_psd_panel,1000,600)
        self.Center(True)
        self.Show()

        # create a pubsub receiver for refresh after data capture / ref. link on threads
        Publisher.subscribe(self.updateDisplay, "update")
    
    def OnCombo(self,event):
        #A happens when a station is selected
        self.label.SetLabel("You selected "+self.combobox.GetValue()+" from Combobox") 

    def run(self):
        """Main loop for the application"""
        self.app.MainLoop()
        
    def updateDisplay(self, msg):
        """
        Receives data from thread and updates the display (graph and statusbar)
        """
        try:
            self.canvas.draw()
            self.status_display(msg.data)
        except:
            pass
        

    def get_axes(self):
        return self.axes

    def status_display(self, message, level=0, field=0):
        if level == 1:
            wx.CallAfter(self.status_display, message)
        elif level == 2:
            wx.CallAfter(Publisher.sendMessage, 'Update', arg1 = message)
            #wx.CallAfter(Publisher.sendMessage, message)
        else:
            self.status_bar.SetStatusText(message,field)

    def on_close(self, event):
        """Requested to close by the user"""
        self.on_exit(True) ##A
        #self.controller.on_close()  ##A ~ calls itself? but exits also. used the on_exit instead for message dialog first

    def close(self):
        """Requested to close by the controller"""
        #self.app.Exit()   ##A ~ commented because 'App' object has no attribute 'Exit'
        self.Destroy()

    def on_exit(self, event):
        self.status_display("This is supersid signing off...")
        dlg = wx.MessageDialog(self,
                               'Are you sure to quit supersid?', 'Please Confirm',
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            #self.Close(True)   ##A 
            self.Destroy()      ##A

    def on_plot(self, event):
        """Save current buffers (raw) and display the data using supersid_plot.
        Using a separate process to prevent interference with data capture"""
        #filenames = self.controller.save_current_buffers(log_format = 'supersid_format')
        #print("plotting", filenames)
        #SSP.do_main(filenames)
        """Select multiple files and call the supersid_plot module for display"""
        filedialog = wx.FileDialog(self, message = 'Choose files to plot',
                                   defaultDir = self.controller.config.data_path,
                                   defaultFile = '',
                                   wildcard = 'Supported filetypes (*.csv) |*.csv',
                                   style = wx.FD_OPEN | wx.FD_MULTIPLE) #A wx.OPEN lang before

        if filedialog.ShowModal() == wx.ID_OK:         
            filelist = ""
            for u_filename in filedialog.GetFilenames():
                filelist = str(filelist + "../Data/" + str(u_filename) + ",")
            filelist = filelist.rstrip(',') # remove last comma

            ssp = SSP.SUPERSID_PLOT()
            ssp.plot_filelist(filelist)
    def on_plot_files(self, event):
        """Select multiple files and call the supersid_plot module for display"""
        filedialog = wx.FileDialog(self, message = 'Choose files to plot',
                                   defaultDir = self.controller.config.data_path,
                                   defaultFile = '',
                                   wildcard = 'Supported filetypes (*.csv) |*.csv',
                                   style = wx.OPEN | wx.FD_MULTIPLE) #A wx.OPEN lang before

        if filedialog.ShowModal() == wx.ID_OK:         
            filelist = ""
            for u_filename in filedialog.GetFilenames():
                filelist = str(filelist + "../Data/" + str(u_filename) + ",")
            filelist = filelist.rstrip(',') # remove last comma

            ssp = SSP.SUPERSID_PLOT()
            ssp.plot_filelist(filelist)
        
    def on_save_buffers(self, event):
        """Call the Controller for writing unfiltered/raw data to file"""
        self.controller.save_current_buffers(log_type=RAW)
    
    def on_save_filtered(self, event):
        """Call the Controller for writing filtered data to file"""
        self.controller.save_current_buffers('current_filtered.csv', FILTERED)
        
    def on_about(self, event):
        """Open an About message box"""
        info = wx.AboutDialogInfo()
        info.SetIcon(wx.Icon('supersid_icon.png', wx.BITMAP_TYPE_PNG))
        info.SetName('SuperSID')
        info.SetDescription(self.controller.about_app())
        info.SetCopyright('(c) Stanford Solar Center and Eric Gibert')
        wx.AboutBox(info)

    def on_click(self, event): # MLP mouse event
        """Following user click on the graph, display associated information in statusbar"""
        if event.inaxes:
            strength = pow(10, (event.ydata/10.0))
            message = "frequency=%.0f  " % event.xdata + " power=%.3f  " % event.ydata  + " strength=%.0f" % strength
            self.status_display(message, field = 1)


    def display_message(self, message="message...", sender="SuperSID"):
        """For any need to display a MessageBox - to review for better button/choice management"""
        status = wx.MessageBox(message,
                              sender,
                              wx.CANCEL | wx.ICON_QUESTION)
        if status == wx.YES:
            return 1 #RETRY
        elif status == wx.NO:
            return 1 #SKIP
        elif status == wx.CANCEL:
            return 1 #STOP
        else:
            return 0
        
    def get_psd(self, data, NFFT, FS):
        """By calling 'psd' within axes, it both calculates and plots the spectrum"""
        try:
            Pxx, freqs = self.axes.psd(data, NFFT = NFFT, Fs = FS)
        except wx.PyDeadObjectError:
            exit(3)
        return Pxx, freqs

    def on_qdc(self, event):
        self.controller.create_qdc()
