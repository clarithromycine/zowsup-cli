from axolotl.state.taskmsgstore import TaskMsgStore

import time
import logging
from typing import Any, Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class LiteContactStore(TaskMsgStore):

    def __init__(self, dbConn):
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn        
        dbConn.execute("CREATE TABLE IF NOT EXISTS contact(_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "name TEXT,"
                "jid TEXT,"
                "lid TEXT,"
                "tctoken BLOB,"
                "tctoken_ts INTEGER,"
                "timestamp INTEGER);")                                    
                    
    def updateContact(self, jid,lid, name=None):

        #检查jid和lid都要满足特定的条件，否则不加到联系人库里面
        if jid is not None and not jid.endswith("s.whatsapp.net"):
            return None
        
        if lid is not None and not lid.endswith("lid"):
            return None
                                            
        if not self.findContact(jid,lid):            
            q = "INSERT INTO contact(name,jid,lid,timestamp) VALUES(?,?,?,?)"
            self.dbConn.cursor().execute(q, (name, jid,lid,int(time.time())))
            self.dbConn.commit()
            return jid     
        else:
            if name is not None:
                self.updateName(jid,lid,name)

        return None


    def findContact(self,jid=None,lid=None):      

        if jid is None and lid is None:
            return False
        
        found = False
        
        if  lid is not None:
            if not lid.endswith("lid"):
                return False
            q = "SELECT lid FROM contact WHERE lid = ?"
            c = self.dbConn.cursor()
            c.execute(q, (lid, ))     
            if c.fetchone():                                      
                found = True
        
        if not found:                
            if jid is not None:
                if not jid.endswith("s.whatsapp.net"):
                    return False
                                
                q = "SELECT jid FROM contact WHERE jid = ?"
                c = self.dbConn.cursor()
                c.execute(q, (jid, ))
                if c.fetchone():                                      
                    found = True
                  
        return found
                                                    
    def removeContact(self,jid,lid):

        if jid is not None:
            q = "DELETE FROM contact where jid = ?"
            self.dbConn.cursor().execute(q, (jid,))
            self.dbConn.commit()        

        elif lid is not None:
            q = "DELETE FROM contact where lid = ?"
            self.dbConn.cursor().execute(q, (lid,))
            self.dbConn.commit()        

        return True
    
    def getAllContact(self):
        #返回一个jid数组        
        q = "SELECT jid,lid FROM contact"
        c = self.dbConn.cursor()
        c.execute(q)

        results = c.fetchall()
        jids = []
        for item in results:
            jids.append({
                "jid":item[0],
                "lid":item[1]
            })

        return jids
    
    def updateName(self,jid=None,lid=None,name=None):
        if name is None:
            return 
        
        if self.findContact(jid,lid):   
            if jid is not None:     
                q = "UPDATE contact SET name=? WHERE jid=?"
                self.dbConn.cursor().execute(q, (name,jid))            
            elif lid is not None:
                q = "UPDATE contact SET name=? WHERE lid=?"
                self.dbConn.cursor().execute(q, (name,lid))   
            self.dbConn.commit()
        else:
            self.updateContact(jid,lid,name=name)

        return True
            
    def updateTctoken(self, node):  #直接处理xmpp node，

        tctoken = None
        tokens = node.getChild("tokens")
        if tokens:
            token = tokens.getAllChildren()[0]
            if token["type"]=="trusted_contact":            
                if node["from"].endswith("lid"):
                    jid = node["sender_pn"]
                    lid = node["from"]
                else:
                    jid = node["from"]
                    lid = node["sender_lid"]
                tctoken = token.getData()
                tctoken_ts=int(token.getAttributeValue("t"))
    
        if tctoken is None:
            return 
        
        if tctoken_ts is None:
            tctoken_ts = int(time.time())


        if self.findContact(jid,lid):
            if jid is not None:
                q = "UPDATE contact SET tctoken=?,tctoken_ts=? WHERE jid=?"
                self.dbConn.cursor().execute(q, (tctoken,tctoken_ts,jid))            
            elif lid is not None:
                q = "UPDATE contact SET tctoken=?,tctoken_ts=? WHERE lid=?"
                self.dbConn.cursor().execute(q, (tctoken,tctoken_ts,lid))
            self.dbConn.commit()
        else:            
            q = "insert into contact(jid,lid,tctoken,tctoken_ts) VALUES(?,?,?,?)"
            self.dbConn.cursor().execute(q, (jid,lid,tctoken,tctoken_ts))                
            self.dbConn.commit()
                                            
        return True                        

    def getTctoken(self,jid=None,lid=None):               

        token = None

        if token is None and jid is not None:
            q = "SELECT tctoken FROM contact WHERE jid = ?"
            c = self.dbConn.cursor()
            c.execute(q, (jid, ))                                
            result = c.fetchone()
            token = result[0] if result else None
                    
        if token is None and lid is not None:
            q = "SELECT tctoken FROM contact WHERE lid = ?"
            c = self.dbConn.cursor()
            c.execute(q, (lid,))                                
            result = c.fetchone()
            token = result[0] if result else None            

        return token        
    
    def removeTctoken(self,jid=None,lid=None):

        if jid is not None:
            q = "UPDATE contact SET tctoken=NULL,tctoken_ts=NULL WHERE jid=?"
            self.dbConn.cursor().execute(q, (jid,))
        
        elif lid is not None:
            q = "UPDATE contact SET tctoken=NULL,tctoken_ts=NULL WHERE lid=?"
            self.dbConn.cursor().execute(q, (lid,))

        self.dbConn.commit()
        return True   