'''
This module contains the ComicBook class, which represents a comic book
from ComicRack that we are scraping data into.

@author: Cory Banack
'''
import re
import log
from time import strftime
from utils import sstr
import db
import utils
from dbmodels import IssueRef
import fnameparser

# coryhigh: use this
#   clr   clr.AddReference("Ionic.Zip.dll") # a 3rd party dll
#   from Ionic.Zip import ZipFile #@UnresolvedImport
#   from System.IO import Directory, File
#   def delegate2(): # coryhigh: delete
#      zip = r"K:\xmlstuff\comic.cbz";
#      xml = r"ComicInfo.xml" 
#      
#      # grab the default (i.e. english) zip file, unzip it, and grab the
#      # xml file from inside.  parse that to obtain default i18n strings.
#      with ZipFile.Read(zip) as zipfile:
#         zipfile.AddEntry("cory.txt", "this is some sample text")
#         zipfile.Save(zip+".zip")

#==============================================================================
class ComicBook(object):
   '''
   This class is a wrapper for the ComicRack ComicBook object, which adds 
   additional, scraper-oriented functionality to the object, and provides 
   read-only access to some of its data.
   '''
   
   # This is the magic 'tag' string we use (in the "Tags" or "Notes" fields of 
   # this comic book) to denote that this comic should always be skipped 
   # automatically, instead of scraped.  Despite the CV in the name, 
   # this is a database independent magic value.
   CVDBSKIP = 'CVDBSKIP'

   #===========================================================================   
   def __init__(self, cr_book):
      '''
      Initializes this ComicBook object based on an underlying ComicRack 
      ComicBook object (the cr_book) parameter.
      '''
      
      if not cr_book:
         raise Exception("invalid backing comic book")
      self.__cr_book = cr_book
      
      if self.__cr_book.Id is None:
         raise Exception("invalid unique id string")
      
      # obtain values self.__series_s and self.__issue_num_s
      self.__set_series_and_issuenum()

   
   #===========================================================================   
   # the series name of this comicbook as a string.  not None, maybe empty.
   series_s = property( lambda self : self.__series_s )
   
   # the issue 'number' of this comicbook as a string. not None. maybe empty.
   issue_num_s = property( lambda self : self.__issue_num_s )
   
   # the volume (start year) of this comic book, as an integer >= 0, 
   # or else -1 to indicate a blank value.
   volume_n = property( lambda self :  self.__cr_book.ShadowVolume 
      if self.__cr_book.ShadowVolume >= -1 else -1   )
   
   # the year (of publication) of this comic book, as an integer >= 0, 
   # or else -1 to indicate a blank value.
   year_n = property( lambda self : self.__cr_book.ShadowYear 
      if self.__cr_book.ShadowYear >= -1 else -1   )
   
   # the format of this comic book, as a string, or "" if empty.  Not None.
   format_s = property( lambda self : self.__cr_book.ShadowFormat
      if self.__cr_book.ShadowFormat else "" )
   
   # a comma separated string listing the tags associated with this comic book.   
   # maybe be empty, but will not be None.
   tags_s = property( lambda self : self.__cr_book.Tags 
      if self.__cr_book.Tags else "" )
   
   # the notes string for this comic book.  Mayb be "", but will not be None.
   notes_s = property( lambda self : self.__cr_book.Notes
      if self.__cr_book.Notes else "" )
   
   # the name of this comic book's backing file, including its file extension.
   # will not be None, will be empty if book is fileless.
   filename_s = property(lambda self : "" if 
      self.__cr_book.FileNameWithExtension is None else 
      self.__cr_book.FileNameWithExtension)
   
   # the number of pages in this comic book.  0 or higher.
   page_count_n = property( lambda self : 0 if 
       not self.__cr_book.PageCount or self.__cr_book.PageCount < 0
       else self.__cr_book.PageCount )
   
   
   
   
   # the unique id string associated with this comic book's series.  all comic
   # books that appear to be from the same series will have the same id string,
   # which will be different for each series. will not be null or None.
   unique_series_s = property( lambda self : self.__unique_series_s() )  

   # an IssueRef object, if this book has been scraped before, or None if not 
   issue_ref = property( lambda self : None if 
      self.__extract_issue_ref() == 'skip' else self.__extract_issue_ref() )
    
   # true if this book as has been marked to "skip forever" (the scraper should
   # silently skip this book if this value is true, regardless of self.issue_ref
   skip_b = property( lambda self : self.__extract_issue_ref() == 'skip' ) 


   #==========================================================================
   def create_page_image(self, scraper, page_index):
      ''' 
      Retrieves an COPY of a single page (a .NET "Image" object) for this 
      ComicBook.  Returns None if the requested page could not be obtained.
      
      scraper --> the ScraperEngine object that is currently running 
      page_index --> the index of the page to retrieve; a value on the range
                  [0, n-1], where n is self.page_count_n.
      '''
      fileless = self.filename_s.strip() == ""
      page_image = None
      if fileless or page_index < 0 or page_index >= self.page_count_n:
         page_image = None
      else:
         page_image = \
            scraper.comicrack.App.GetComicPage( self.__cr_book, page_index )
         page_image = utils.strip_back_cover(page_image)
      return page_image
   

   #===========================================================================
   def skip_forever(self, scraper):
      ''' 
      This method causes this book to be marked with the magic CVDBSKIP
      flag, which means that from now on, self.issue_ref will always be 
      "skip", which tells the scraper to automatically skip over this book
      without even asking the user.  
      '''
      
      # try to make everyone happy here: if notes and tags "rescrape saving"
      # are both turned on, or both turned off, then this command should just
      # write CVDBSKIP to both of them (users who turn off both still might
      # want CVDBSKIP to work!) otherwise, use the values of these 2 prefs to
      # determine which fields to write the CVDBSKIP to.
      
      notes = scraper.config.rescrape_notes_b
      tags = scraper.config.rescrape_tags_b
      
      if notes == tags or tags:
         self.__cr_book.Tags = self.__update_tags_s(self.__cr_book.Tags, None)
         log.debug("Added ", ComicBook.CVDBSKIP, " flag to comic book 'Tags'")
      
      if notes == tags or notes:
         self.__cr_book.Notes =self.__update_notes_s(self.__cr_book.Notes, None)
         log.debug("Added ", ComicBook.CVDBSKIP, " flag to comic book 'Notes'")
         

   # =============================================================================
   def __extract_issue_ref(self): 
      '''
      This method looks in the tags and notes fields of the this book for 
      evidence that the it has been scraped before.   If possible, it will 
      construct an IssueRef based on that evidence, and return it. If not, 
      it will return None, or the string "skip" (see below).   
      
      If the user has manually added the magic CVDBSKIP flag to the tags or 
      notes for this book, then this method will return the string "skip", 
      which should be interpreted as "never scrape this book".
      '''
      
      # check for the magic CVDBSKIP skip flag
      skip_found = re.search(r'(?i)'+ComicBook.CVDBSKIP, self.tags_s)
      if not skip_found:
         skip_found = re.search(r'(?i)'+ComicBook.CVDBSKIP, self.notes_s)
      retval = "skip" if skip_found else None
   
      if retval is None:   
         # if no skip tag, see if there's a key tag in the tags or notes
         issue_key = db.parse_key_tag(self.tags_s)
         
         if issue_key == None:
            issue_key = db.parse_key_tag(self.notes_s)
      
         if issue_key != None:
            # found a key tag! convert to an IssueRef
            retval = IssueRef(self.issue_num_s, issue_key)
   
      return retval
   

   #==========================================================================
   def __unique_series_s(self):
      '''
      Gets the unique series name for this ComicBook.   This is a special 
      string that will be identical for (and only for) any comic books that 
      "appear" to be from the same series.
      
      The unique series name is meant to be used internally (i.e. the key for
      a map, or for grouping ComicBooks), not for displaying to users.
      
      This value is NOT the same as the series_s property.
      '''
      sname = '' if not self.series_s else self.series_s
      if sname and self.format_s:
         sname += self.format_s
      sname = re.sub('\W+', '', sname).lower()

      svolume = ''
      if sname:
         if self.volume_n and self.volume_n > 0:
            svolume = "[v" + sstr(self.volume_n) + "]"
      else:
         # if we can't find a name at all (very weird), fall back to the
         # memory ID, which is be unique and thus ensures that this 
         # comic doesn't get lumped in to the same series choice as any 
         # other unnamed comics! 
         sname = "uniqueid-" + utils.sstr(id(self))
      return sname + svolume


   #===========================================================================
   def copy_issue_details(self, issue, scraper):
      '''
      Copies all data in the given issue into this ComicBook object, respecting 
      all of the overwrite/ignore rules defined in the given scraper's
      Configuration object.  
      
      Note that these changes get pushed down right into the backing 
      ComicRack comic book object, so this method makes real modifications that 
      the user will actually see in the comics in ComicRack. 
      
      As a side-effect, some detailed debug log information about the new values
      is also emitted.
      '''
      
      log.debug("setting values for this comic book ('*' = changed):")
      config = scraper.config
      cb = ComicBook
      book = self.__cr_book
      
      # series ---------------------
      value = cb.__massage_new_string("Series", issue.series_name_s, \
         book.Series, config.update_series_b, config.ow_existing_b, \
         True ) # note: we ALWAYS ignore blanks for 'series'!
      if ( value is not None ) :  book.Series = value
      
      # issue number ---------------
      value = cb.__massage_new_string("Issue Number", issue.issue_num_s, \
         book.Number, config.update_number_b, config.ow_existing_b, \
         True ) # note: we ALWAYS ignore blanks for 'issue number'!
      if ( value is not None ) :  book.Number = value
      
      # title ----------------------
      value = cb.__massage_new_string("Title", issue.title_s, book.Title, \
         config.update_title_b, config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Title = value
         
      # alternate series -----------
      value = cb.__massage_new_string("Alt/Arc", \
         ', '.join(issue.alt_series_names), book.AlternateSeries, \
         config.update_alt_series_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.AlternateSeries = value
      
      # summary --------------------
      value = cb.__massage_new_string("Summary", issue.summary_s, \
         book.Summary, config.update_summary_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Summary = value
      
      # year -----------------------
      value = cb.__massage_new_number("Year", issue.year_n, \
         book.Year, config.update_year_b, config.ow_existing_b, \
         True, -1, lambda x : x > 0 ) # note: we ALWAYS ignore blanks for 'year'
      if ( value is not None ) :  book.Year = value
      
      # month ----------------------
      def remap(month):
         # months 1 to 12 are straightforward, but the remaining possible
         # values (listed below) must be converted into the range 1-12:
         # 13 - Spring   18 - None      23 - Sep/Oct   28 - Apr/May
         # 14 - Summer   19 - Jan/Feb   24 - Nov/Dec   29 - Jun/Jul
         # 15 - Fall     20 - Mar/Apr   25 - Holiday   30 - Aug/Sep
         # 16 - Winter   21 - May/Jun   26 - Dec/Jan   31 - Oct/Nov
         # 17 - Annual   22 - Jul/Aug   27 - Feb/Mar  
         remap={ 1:1, 26:1, 2:2, 19:2, 3:3, 13:3, 27:3, 4:4, 20:4, 5:5, 28:5, \
                 6:6, 14:6, 21:6, 7:7, 29:7, 8:8, 22:8, 9:9, 15:9, 30:9, 10:10,\
                 23:10, 11:11, 31:11, 12:12, 16:12, 24:12, 25:12 }
         retval = -1;
         if month in remap:
            retval = remap[month]
         return retval
         
      value = cb.__massage_new_number("Month", issue.month_n, book.Month, \
         config.update_month_b, config.ow_existing_b, True, -1, \
         lambda x : x>=1 and x <=12, remap ) # ALWAYS ignore blanks for 'month'
      if ( value is not None ) :  book.Month = value
      
      # volume --------------------
      value = cb.__massage_new_number("Volume", issue.start_year_n, \
      book.Volume, config.update_volume_b, config.ow_existing_b, \
      config.ignore_blanks_b, -1, lambda x : x > 0 )
      if ( value is not None ) :  book.Volume = value
       
      # if we found an imprint for this issue, the user may prefer that the 
      # imprint be listed as the publisher (instead). if so, make that change
      # before writing the 'imprint' and 'publisher' fields out to the book:
      if not config.convert_imprints_b and issue.imprint_s:
         issue.publisher_s = issue.imprint_s
         issue.imprint_s = ''                                   
            
      # imprint -------------------
      value = cb.__massage_new_string("Imprint", issue.imprint_s, \
         book.Imprint, config.update_imprint_b, \
         config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Imprint = value
            
      # publisher -----------------
      value = cb.__massage_new_string("Publisher", issue.publisher_s, \
         book.Publisher, config.update_publisher_b, \
         config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Publisher = value
      
      # characters ----------------
      value = cb.__massage_new_string("Characters", \
         ', '.join(issue.characters), book.Characters, \
         config.update_characters_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Characters = value
      
      # teams ----------------
      value = cb.__massage_new_string("Teams", \
         ', '.join(issue.teams), book.Teams, config.update_teams_b, \
         config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Teams = value
      
      # locations ----------------
      value = cb.__massage_new_string( \
         "Locations", ', '.join(issue.locations), \
         book.Locations, config.update_locations_b,\
         config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Locations = value
      
      # writer --------------------
      value = cb.__massage_new_string("Writers", \
         ', '.join(issue.writers), book.Writer, \
         config.update_writer_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Writer = value
         
      # penciller -----------------
      value = cb.__massage_new_string("Pencillers", \
         ', '.join(issue.pencillers), book.Penciller, \
         config.update_penciller_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Penciller = value
      
      # inker ---------------------
      value = cb.__massage_new_string("Inkers", \
         ', '.join(issue.inkers), book.Inker, \
         config.update_inker_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Inker = value
         
      # colorist -----------------
      value = cb.__massage_new_string("Colorists", \
         ', '.join(issue.colorists), book.Colorist, \
         config.update_colorist_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Colorist = value
         
      # letterer -----------------
      value = cb.__massage_new_string("Letterers", \
         ', '.join(issue.letterers), book.Letterer, \
         config.update_letterer_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Letterer = value
         
      # coverartist --------------
      value = cb.__massage_new_string("CoverArtists", \
         ', '.join(issue.cover_artists), book.CoverArtist, \
         config.update_cover_artist_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.CoverArtist = value
         
      # editor -------------------   
      value = cb.__massage_new_string("Editors", \
         ', '.join(issue.editors), book.Editor, \
         config.update_editor_b, config.ow_existing_b, \
         config.ignore_blanks_b )
      if ( value is not None ) :  book.Editor = value
   
      # webpage ----------------
      value = cb.__massage_new_string("Webpage", issue.webpage_s, \
         book.Web, config.update_webpage_b, \
         config.ow_existing_b, config.ignore_blanks_b )
      if ( value is not None ) :  book.Web = value
      
      # rating -----------------------
      value = cb.__massage_new_number("Rating", issue.rating_n, \
         float(book.CommunityRating), config.update_rating_b, 
         config.ow_existing_b, config.ignore_blanks_b, 0.0,
         lambda x: x >= 0 and x <= 5, lambda x : max(0.0,min(5.0,x)) )
      if ( value is not None ) :  book.CommunityRating = value
         
      # tags ----------------------
      new_tags = self.__update_tags_s(book.Tags, issue.issue_key)
      value = cb.__massage_new_string("Tags", new_tags, \
         book.Tags, config.rescrape_tags_b, True, False )
      if ( value is not None ) :  book.Tags = value
      
      # notes --------------------
      new_notes = self.__update_notes_s(book.Notes, issue.issue_key)
      value = cb.__massage_new_string("Notes", new_notes, \
         book.Notes, config.rescrape_notes_b, True, False )
      if ( value is not None ) :  book.Notes = value
      
      del value
   
      self.__maybe_download_thumbnail(issue, scraper) 
   
   
   #===========================================================================
   def __update_tags_s(self, tagstring_s, issue_key):
      '''
      Returns the given comma separated tag string, but with a "key tag" for 
      the given issue_key added in (iff key tags are supported by the current 
      database implementation.)  If the given string already contains a valid 
      key tag, the tag will be REPLACED with the new one, otherwise the new key 
      tag will be appended to the end of the string.
      
      If the given issue_key is None, the tag string will be updated with the
      magic CVDBSKIP tag instead of a regular key tag.
      
      This method never returns None. 
      '''
      updated_tagstring_s = None   # our return value
      
      # 1. clean up whitespace and None in our tagstring parameter
      tagstring_s = tagstring_s.strip() if tagstring_s else ''
      
      key_tag_s = db.create_key_tag_s(issue_key) \
         if issue_key != None else ComicBook.CVDBSKIP 
      if key_tag_s and tagstring_s:
         # 2. we have both a new key tag AND a non-empty tagstring; find and 
         #    replace the existing tag (if it exists in the tagtring) 
         #    with the new one. 
         matches = False
         prev_issue_key = db.parse_key_tag(tagstring_s)
         if prev_issue_key:
            prev_key_tag_s = db.create_key_tag_s(prev_issue_key)
            if prev_key_tag_s:
               regexp = re.compile(r"(?i)" + prev_key_tag_s)
               matches = regexp.search(tagstring_s)
         if matches:
            # 2a. yup, found an existing key tag--replace it with the new one
            updated_tagstring_s = re.sub(regexp, key_tag_s, tagstring_s)
         else:
            # 2b. nope, no previous key tag found--just append the new key tag
            if tagstring_s[-1] == ",":
               tagstring_s = tagstring_s[:-1]
            updated_tagstring_s = tagstring_s +", " + key_tag_s
      elif key_tag_s:
         # 3. no previous tagstring, so the key tag *becomes* the new tagstring
         updated_tagstring_s = key_tag_s
      else:
         # 4. there's no key tag available, so don't change the tagstring.
         updated_tagstring_s = tagstring_s
   
      return updated_tagstring_s
   
   
   #===========================================================================
   def __update_notes_s(self, notestring_s, issue_key):
      '''
      Returns a copy of the given comic book note string, but with a "key tag" 
      for the given issue_key appended onto the end (iff key tags are
      supported by the current database implementation.)  If the given 
      notes string already contains a valid key tag, the existing tag will be 
      REPLACED with the new one.
      
      If the given issue_key is None, the note string will be updated with the
      magic CVDBSKIP tag instead of a regular key tag.
      
      This method never returns None. 
      '''
      updated_notestring_s = None # our return value
      
      # 1. clean up whitespace and None in our notestring parameter
      notestring_s = notestring_s.strip() if notestring_s else ''
      
      key_tag_s = db.create_key_tag_s(issue_key) \
         if issue_key != None else ComicBook.CVDBSKIP
      key_note_s = 'Scraped metadata from {0} [{1}] on {2}.'.format(
         "ComicVine", key_tag_s, strftime(r'%Y.%m.%d %X')) if key_tag_s else ''
         
      if key_note_s and notestring_s:
         # 2. we have both a new key-note (based on the key tag), AND a 
         #    non-empty notestring; find and replace the existing key-note (if 
         #    it exists in the notestring) with the new one. 
         matches = False
         prev_issue_key = db.parse_key_tag(notestring_s)
         if prev_issue_key:
            prev_key_tag = db.create_key_tag_s(prev_issue_key)
            if prev_key_tag:
               regexp = re.compile(
                  r"(?i)Scraped.*?"+prev_key_tag+".*?[\d\.]{8,} [\d:]{6,}\.")                                   
               matches = regexp.search(notestring_s) 
         if matches:
            # 2a. yup, found an existing key-note--replace it with the new one
            updated_notestring_s = re.sub(regexp, key_note_s, notestring_s)
         else:
            # 2b. nope, no previous key-note found.  try looking for the key
            #     tag on it's own (i.e. if the user added it by hand)
            if prev_issue_key:
               prev_key_tag = db.create_key_tag_s(prev_issue_key)
               if prev_key_tag:
                  regexp = re.compile(r"(?i)" + prev_key_tag)
                  matches = regexp.search(notestring_s)
            if matches:
               # 2c. yup, found a key tag--replace it with the new one
               updated_notestring_s = re.sub(regexp, key_tag_s, notestring_s)
            else:
               # 2b. nope, no previous key found--just append the new key-note
               updated_notestring_s = notestring_s + "\n\n" + key_note_s 
      elif key_note_s:  
         # 3. no previous notestring, so the key-note *becomes* the new string
         updated_notestring_s = key_note_s
      else:
         # 4. there's no key tag available, so don't change the tagstring.
         updated_notestring_s = notestring_s
   
      return updated_notestring_s
   
   
   #===========================================================================
   def __maybe_download_thumbnail(self, issue, scraper):
      '''
      Iff this is a 'fileless' ComicBook, this method downloads and stores a
      cover image into it (assuming the given scraper's config settings permit.)
      Otherwise, this method does nothing.
      
      'book' -> the book whose thumbnail we might update
      'issue' -> the Issue for the book that we are updating
      'scraper' -> the ScraperEnginer that's current running
      '''
      
      # coryhigh: this has to go into comicrack specific code!
      config = scraper.config
      label = "Thumbnail"
      already_has_thumb = self and self.__cr_book.CustomThumbnailKey
      book_is_fileless = self and not self.__cr_book.FilePath
      
      # don't download the thumbnail if the book has a backing file (cause that's
      # where the thumbnail will come from!) or if the user has specified in 
      # config that we shouldn't.
      if not book_is_fileless or not config.download_thumbs_b or \
               (already_has_thumb and config.preserve_thumbs_b):
            log.debug("-->  ", label.ljust(15), ": --- skipped ---")
      else:
         # get the url for this issue's cover art.  check to see if the user
         # picked an alternate cover back when they closed the IssueForm, and if
         # not, just grab the url for the default cover art.
         url = None
         alt_cover_key = sstr(issue.issue_key)+"-altcover"
         if alt_cover_key in config.session_data_map:
            url = config.session_data_map[alt_cover_key]
         if not url and len(issue.image_urls):  
            url = issue.image_urls[0]
            
         if not url:
            # there is no image url available for this issue 
            log.debug("-->  ", label.ljust(15),": --- not available! ---")
         else:
            image = db.query_image(url)
            if not image:
               log.debug("ERROR: couldn't download thumbnail: ", url)
            else:
               cr = scraper.comicrack.App
               success = cr.SetCustomBookThumbnail(self.__cr_book, image)
               if success:
                  # it worked!
                  log.debug("--> *", label.ljust(15),": ", url)
               else:
                  log.debug("ERROR: comicrack can't set thumbnail!")
   
   
   
   #===========================================================================
   @staticmethod 
   def __massage_new_string( 
         label, new_value, old_value, update, overwrite, ignoreblanks):
      ''' 
      Returns a string value that should be copied into our backing ComicBook
      object, IFF that string value is not None.   Uses a number of rules to
      decide what value to return.
      
      label - a human readable description of the given string being changed.
      new_value - the proposed new string value to copy over.
      old_value - the original value that the new value would copy over.
      update - if false, this method always returns None
      overwrite - whether it's acceptable to overwrite the old value with the
                  new value when the old value is non-blank.
      ignoreblanks - if true, we'll never overwrite an old non-blank value
                     with a new, blank value..
      ''' 
      
      # first, a little housekeeping so that we stay really robust
      if new_value is None:
         new_value = ''
      if old_value is None:
         old_value = ''
      if not isinstance(new_value, basestring) or \
         not isinstance(old_value,basestring):
         raise TypeError("wrong types for this method (" + label +")")
      old_value = old_value.strip();
      new_value = new_value.strip();
      
      # now decide about whether or not to actually do the update
      # only update if all of the following are true:
      #  1) the update option is turned on for this particular field
      #  2) we can overwrite the existing value, or there is no existing value
      #  3) we're not overwriting with a blank value unless we're allowed to
      retval = None;      
      if update and (overwrite or not old_value) and \
         not (ignoreblanks and not new_value):
          
         retval = new_value
         
         marker = ' '
         if old_value != new_value:
            marker = '*'
         
         chars = retval.replace('\n', ' ')
         if len(chars) > 70:
            chars = chars[:70] + " ..."
         log.debug("--> ", marker, label.ljust(15), ": ", chars)
      else:
         log.debug("-->  ", label.ljust(15), ": --- skipped ---")
      return retval
   
   
   
   #===========================================================================
   @staticmethod 
   def __massage_new_number(label, new_value, old_value, update, overwrite, \
      ignoreblanks, blank_value, is_valid=None, remap_invalid=None):
      ''' 
      Returns an number (int or float) value that should be copied into our 
      backing ComicBook object, IFF that value is not None.   Uses a number of 
      rules to decide what value to return.
      
      label - a human readable description of the given number being changed.
      new_value - the proposed new number value to copy over.
      old_value - the original value that the new value would copy over.
      update - if false, this method always returns None
      overwrite - whether it's acceptable to overwrite the old value with the
            new value when the old value is non-blank.
      ignoreblanks - if true, we'll never overwrite with an old non-blank value
            with a new, blank value.
      blank_value - the number value that should be considered 'blank' (0? -1?)
      is_valid - an optional single argument function that decides if the given
            int return value is valid.  If not, it is changed to 'blank_value' 
            before it is returned, OR if possible it is remapped with...
      remap_invalid - an optional single argument function that converts the 
            given invalid return value (according to 'is_valid') into a 
            new, valid return value.
      ''' 
      
      
      # first, a little housekeeping so that we stay really robust
      if new_value is None:
         new_value = blank_value;
      if old_value is None:
         old_value = blank_value;
      if type(blank_value) != int and type(blank_value) != float:
         raise TypeError("wrong type for blank value");
      if type(old_value) != int and type(old_value) != float:
         raise TypeError("wrong type for old value");
      if type(old_value) != type(blank_value):
         raise TypeError("blank type is invalid type");
      if type(old_value) != type(new_value):
         try:
            if isinstance(old_value, int):
               new_value = int(new_value)
            else:
               new_value = float(new_value)
         except:
            log.debug("--> WARNING: can't convert '", new_value,
                "' into a ", type(old_value) )
            new_value = blank_value
            
      # check for (and possibly repair) the validity of the new_value
      if is_valid:
         if not is_valid(new_value):
            if remap_invalid:  
               new_value = remap_invalid(new_value)
         if not is_valid(new_value):
            new_value = blank_value
           
      # now decide about whether or not to actually do the update
      # only update if all of the following are true:
      #  1) the update option is turned on for this particular field
      #  2) we can overwrite the existing value, or there is no existing value
      #  3) we're not overwriting with a blank value unless we're allowed to
      retval = None;      
      if update and (overwrite or old_value == blank_value) and \
         not (ignoreblanks and new_value == blank_value):
         retval = new_value
         
         marker = ' '
         if old_value != new_value:
            marker = '*'
            
         if retval == blank_value:
            log.debug("--> ", marker, label.ljust(15), ": ")
         else: 
            log.debug("--> ", marker, label.ljust(15), ": ", retval)
      else:
         log.debug("-->  ", label.ljust(15), ": --- skipped ---")
         
      # last minute type checking, just to be sure the returned value type is ok
      if retval != None:
         retval = float(retval) if type(old_value) == float else int(retval)
      return retval
   
   
   # ==========================================================================
   def __set_series_and_issuenum(self):
      ''' 
      Occasionally the ComicRack parser doesn't do a good job parsing in the
      series name and issue number (both critical bits of data for our
      purposes!).  Ideally, this would be fixed in ComicRack, but since that
      doesn't seem like it's gonna happen, I'll patch up know problems in this
      method instead.
      '''
      # corynorm: this should figure out the format too?!?
      # 1. first off, if these values have been set in ComicRack, just use them
      #    directly. if this is a Fileless book, these should ALWAYS be set.
      self.__series_s = self.__cr_book.Series.strip() \
         if self.__cr_book.Series else ""
      self.__issue_num_s = self.__cr_book.Number.strip() \
         if self.__cr_book.Number else ""
      
      # 2. if we have no values (as will often be the case with fresh, unscraped
      #    files) we'll use our own filename parsing routine to find them.
      if not self.__series_s or not self.__issue_num_s:
         if self.filename_s:
            extracted = fnameparser.extract(self.filename_s)
            if not self.__series_s:
               self.__series_s = extracted[0]
            if not self.__issue_num_s:
               self.__issue_num_s = extracted[1]