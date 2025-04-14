/*
******************************************************
# This page is to managed the sultan escalation studio
# @author: oswald.bernard@hsbc.com
******************************************************
*/

/*
**************************************************
 * Code Initialization
 *************************************************
 */

 // start the localdb with pouchDB
 let workflowsLocalDB = new PouchDB("workflowsDB");


/*
**************************************************
 * Code LOGIC
 *************************************************
 */

function escalationStudio() {
    return {
        page:"workflows-studio",
        workflows:[],
        questions:[],
        templates:[],
        emailsGroups:[],
        selectedWorkflow:{},
        currentFlow:'',
        flowEditor:null,
        editor:{},
        setNodes(data) {
            console.log(data,"data set nodes")
              this.currentFlow=this.flowEditor
            this.currentFlow.nodeLookupCacheMap = {};
            let completeNodes = data.nodes.map((incompleteNode) => {
                 return this.currentFlow.createNode(incompleteNode);
            });
            let completeEdges = data.edges.map((incompleteEdge) => {
                return this.currentFlow.createEdge(incompleteEdge);
            });
            this.currentFlow.nodes = completeNodes;
            console.log(completeNodes,"completeNodes")
            this.currentFlow.edges = completeEdges;
            this.currentFlow.autoCenter=true
        },
        async init(){
            this.workflows = await this.getAllWorkflows() || []
            this.questions = await getConfig("jaffarConfig","questions")
            this.templates = await getConfig("jaffarTemplates","templates")
            this.emailsGroups = await getConfig("jaffarDirectories","directories")
           },
        getAllWorkflows: async function(){
           this.workflows=[]
           const workflows = await workflowsLocalDB.allDocs({include_docs: true})
           workflows.rows.forEach(x=>this.workflows.push(x.doc))
           return this.workflows = this.workflows.reverse()
        },
        createAWorkflow: async function(){

             _id="WORKFLOW-"+new Date().getTime()
             newNode={id:_id+"1",type:"Trigger"}
             data={
        'id': _id,
        'nodes': [newNode],
        'edges': [],
    }
           this.setNodes(data)
           this.selectedWorkflow={"name":"","_id":_id,"rules":this.currentFlow.toObject()}
           console.log(this.selectedWorkflow,"workflow created")
           this.workflows.push(this.selectedWorkflow)
           await createAWorkflowDB(this.selectedWorkflow)
           this.getAllWorkflows()
        },
        updateAWorkflow: async function(){
                this.selectedWorkflow.rules = this.currentFlow.toObject()
                console.log(this.currentFlow.toObject(),"props")
                rev = await workflowsLocalDB.get(this.selectedWorkflow._id)
                workflow={...this.selectedWorkflow}
                workflow._rev=rev["_rev"]
                console.log(workflow,"d")
                await workflowsLocalDB.put(workflow)
                return alert("Save successful")
        },
        deleteWorkflow: async function(id){
            // call the helper deleteAWorkflow with as a param this.selectedWorkflow._id
            await deleteWorkflow(id)
            this.getAllWorkflows()
        },
        selectWorkflow: function(workflowId){
            this.workflows.forEach((x)=>{if(x._id==workflowId){ this.selectedWorkflow = x}})
            this.setNodes(this.selectedWorkflow.rules)
        },
         // Jaffar config export
        jaffarConfigExport: "",
        prepTheDataForExport() {
        let exportJaffar = {};
        exportJaffar._id = "jaffarEscalationRules";
        exportJaffar.workflows =[];
        this.workflows.forEach(x=>exportJaffar.workflows.push(extractData(x)))
        this.jaffarConfigExport = JSON.stringify(exportJaffar);
        console.log(this.jaffarConfigExport)
        this.page = "export-to-jaffar";
        },
        defaultNode:{id: 1, type: 'Trigger'},
        slideOverOpen: false,
        selectedId: null,
        currentFlowInstance: null,
        animateEdges: function animateEdges(edges){
            this.currentFlowInstance.edges.forEach(edge => edge.animated = !edge.animated)
        },
        handleDrop: function handleDrop(event, node){
            let type = event.dataTransfer.getData('text/plain');
            if (typeof type === undefined || !type) {
                return;
            }
            const newNode = {
                type,
                id: this.genNodeId(),
            };
            this.addNode(newNode, [node.id])
        },
        genNodeId: function getNextNodeId(){return Math.random().toString(16).slice(2)}
    }
}


/*
**************************************************
 *  Code Methods
 *************************************************
 */


 async function createAWorkflowDB(workflow){
 console.log("flow to save",workflow)
    // this function create a new group in the pouchDB. The _id is the name of the group.
    return workflowsLocalDB.put(workflow)
}

async function deleteWorkflow(id){
    // this function delete the groupId in the pouchDB
    group = await workflowsLocalDB.get(id)
        await workflowsLocalDB.remove(group)
        return 
}

async function getConfig(file,key) {
 data = await axios.get('/pc-analytics-jaffar/jaffar/configs/get?file='+file)
 console.log(key)
  return data.data[key];
}

function extractData(obj) {
  let results = [];
  nodes = obj.rules.nodes
  triggers=nodes.shift()


  rule={
  "id":obj._id,
  "name":obj.name,
  "triggers":triggers.data.triggers,
  "actions":nodes.map(x=>x.data)
  }
  return rule;
}