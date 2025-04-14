// ###################################################
//  Javascript controller for the hubsites studio
// ###################################################

// ######## INIT ################################

let hubsiteLocalDB = new PouchDB("hubsiteDB");      

// ######## ALPINEJS #######################

function jaffarEscalationHubsiteStudio(){
    return {
        page:"",
        selectedHubsites:{"_id":"hubsites","hubsites":[]},
        questions:[],
        async init(){
            this.questions = await getConfig("jaffarConfig","questions")
            this.questions = this.questions.filter(x=>x.key=='Location')
            await this.getHubsites()
            this.page="hubsite-studio"
            this.$watch("selectedHubsites", value=>this.updateHubsites(value))
           },
        updateHubsites: async function(){
               rev = await hubsiteLocalDB.get("hubsites")
                group={...this.selectedHubsites}
               group._rev=rev["_rev"]
               await hubsiteLocalDB.put(group)
               return hubsiteLocalDB.put(group)

        },
        getHubsites: async function(){
             try {this.selectedHubsites = await hubsiteLocalDB.get("hubsites")}
             catch (error) {
              this.selectedHubsites = hubsiteLocalDB.put(this.selectedHubsites)
            } finally {
                return
            }
        },
        saveAnswer: function(value){
        let index = this.selectedHubsites.hubsites.indexOf(value);
         index!=-1
        ? this.selectedHubsites.hubsites.splice(index, 1)
        : this.selectedHubsites.hubsites.push(value);
        },
         // Jaffar config export
        jaffarConfigExport: "",
        prepTheDataForExportJaffar() {
        let exportJaffar = {};
        exportJaffar._id = "jaffarEscalationHubsites";
        exportJaffar.hubsites = this.selectedHubsites;
        this.jaffarConfigExport = JSON.stringify(exportJaffar);
        this.page = "export-to-jaffar";
    },
    async importHubsites(){
       selectedHubsites=await getConfig('jaffarHubsites','hubsites')
       console.log(selectedHubsites)
       this.selectedHubsites=selectedHubsites
    }
        
    }
}

// ############## HELPERS ###########################
async function createAHubsiteDB(){
    obj={}
    _id="hubsites"
    obj._id=_id
    return hubsiteLocalDB.put(group)
}

async function deleteAGroup(id){
    // this function delete the groupId in the pouchDB
    group = await hubsiteLocalDB.get(id)
        await hubsiteLocalDB.remove(group)
        return 
}

async function getConfig(file,key) {
 data = await axios.get('/pc-analytics-jaffar/jaffar/configs/get?file='+file)
  return data.data[key];
  }