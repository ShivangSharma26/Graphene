import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import './KnowledgeGraph.css'; // Optional for the overlay panels

// Theme config matching the spec
const THEME = {
  colors: {
    file: '#00E5FF',       // Electric Cyan
    class: '#B388FF',      // Neon Violet
    function: '#FF4081',   // Vivid Pink
    import: '#7C4DFF',     // Deep Indigo
    bgGradientStart: '#0f172a', // Slate 900
    bgGradientMid: '#020617',   // Slate 950
    bgGradientEnd: '#000000'    // Pitch Black
  },
  radius: {
    file: 9,
    class: 7,
    function: 5.5,
    import: 5.5
  }
};

export default function KnowledgeGraph({ data }) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !data || data.nodes.length === 0) return;
    
    // Cleanup previous svg
    d3.select(containerRef.current).selectAll("svg").remove();

    const width = containerRef.current.clientWidth || 800;
    const height = containerRef.current.clientHeight || 600;

    // Deep copy data for D3 mutation
    const nodes = data.nodes.map(d => ({ ...d }));
    const links = data.links.map(d => ({ ...d }));

    const svg = d3.select(containerRef.current)
      .append("svg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", [0, 0, width, height])
      .style("background", `radial-gradient(ellipse at 30% 20%, ${THEME.colors.bgGradientStart} 0%, ${THEME.colors.bgGradientMid} 55%, ${THEME.colors.bgGradientEnd} 100%)`)
      .style("border-radius", "16px")
      .style("border", "1px solid rgba(255,255,255,0.08)")
      .style("overflow", "hidden")
      .on("click", (e) => {
        if (e.target.tagName === 'svg' || e.target.tagName === 'rect') {
          setSelectedNode(null);
          // reset opacities
          svg.selectAll('.graph-node').style("opacity", 1);
          svg.selectAll('.graph-link').style("opacity", 0.35);
        }
      });

    // Invisible rect to catch background zoom/pan events
    svg.append("rect")
      .attr("width", width)
      .attr("height", height)
      .attr("fill", "transparent");

    // Define Glow Filters
    const defs = svg.append("defs");
    
    // Create a glow filter for each node type color
    Object.entries(THEME.colors).forEach(([type, color]) => {
      if (!['file', 'class', 'function', 'import'].includes(type)) return;
      
      const filter = defs.append("filter")
        .attr("id", `glow-${type}`)
        .attr("x", "-50%")
        .attr("y", "-50%")
        .attr("width", "200%")
        .attr("height", "200%");
      
      filter.append("feGaussianBlur")
        .attr("stdDeviation", "3.5")
        .attr("result", "coloredBlur");
        
      const feMerge = filter.append("feMerge");
      feMerge.append("feMergeNode").attr("in", "coloredBlur");
      feMerge.append("feMergeNode").attr("in", "SourceGraphic");
    });

    // Zoom wrapper
    const g = svg.append("g");
    
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on("zoom", (e) => g.attr("transform", e.transform));
      
    svg.call(zoom);

    // Edges
    const link = g.append("g")
      .attr("stroke-opacity", 0.35)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("class", "graph-link")
      .attr("stroke", d => {
        if (d.kind === "imports") return "rgba(124, 77, 255, 0.7)"; // Indigo
        if (d.kind === "defines") return "rgba(0, 229, 255, 0.7)"; // Cyan
        return "rgba(255, 64, 129, 0.7)"; // Calls (Pink)
      })
      .attr("stroke-dasharray", d => d.kind === "calls" ? "3,3" : "none")
      .attr("stroke-width", 1.5);

    // Nodes
    const node = g.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "graph-node")
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended)
      );

    // Draw circles
    node.append("circle")
      .attr("r", d => THEME.radius[d.type] || 5)
      .attr("fill", d => THEME.colors[d.type] || '#fff')
      .attr("stroke", "rgba(255,255,255,0.35)")
      .attr("stroke-width", 0.8)
      .style("filter", d => `url(#glow-${d.type})`)
      .on("mouseover", handleMouseOver)
      .on("mouseout", handleMouseOut)
      .on("click", (e, d) => {
        e.stopPropagation();
        
        // Build detailed data for panel
        const incoming = links.filter(l => l.target.id === d.id || l.target === d.id);
        const outgoing = links.filter(l => l.source.id === d.id || l.source === d.id);
        
        setSelectedNode({ ...d, incoming, outgoing });
        
        // Highlight clicked node
        svg.selectAll('.graph-node').style("opacity", n => n.id === d.id ? 1 : 0.2);
        svg.selectAll('.graph-link').style("opacity", l => 
          (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.05
        );
      });

    // Draw Labels
    node.append("text")
      .text(d => d.label || d.id)
      .attr("x", d => (THEME.radius[d.type] || 5) + 5)
      .attr("y", 3)
      .attr("font-family", "sans-serif")
      .attr("font-size", "10px")
      .attr("fill", "rgba(255,255,255,0.85)")
      .style("pointer-events", "none")
      .style("visibility", d => ['file', 'class'].includes(d.type) ? "visible" : "hidden")
      .attr("class", "node-label");

    // Force Physics
    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(d => {
        if (d.kind === "calls") return 55;
        if (d.kind === "defines") return 45;
        return 90; // imports
      }))
      .force("charge", d3.forceManyBody().strength(-160))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide().radius(d => (THEME.radius[d.type] || 5) + 14));

    simulation.on("tick", () => {
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node.attr("transform", d => `translate(${d.x},${d.y})`);
    });

    // Drag interactions
    function dragstarted(e) {
      if (!e.active) simulation.alphaTarget(0.25).restart();
      e.subject.fx = e.subject.x;
      e.subject.fy = e.subject.y;
    }
    function dragged(e) {
      e.subject.fx = e.x;
      e.subject.fy = e.y;
    }
    function dragended(e) {
      if (!e.active) simulation.alphaTarget(0);
      e.subject.fx = null;
      e.subject.fy = null;
    }

    // Hover interactions
    function handleMouseOver(e, d) {
      d3.select(this).attr("stroke", "white").attr("stroke-width", 1.5);
      
      // Show label if hidden
      d3.select(this.parentNode).select(".node-label").style("visibility", "visible");

      // Dim others
      svg.selectAll('.graph-link')
        .style("opacity", l => (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.1);
        
      svg.selectAll('.graph-node')
        .style("opacity", n => {
          if (n.id === d.id) return 1;
          const isConnected = links.some(l => 
            (l.source.id === d.id && l.target.id === n.id) || 
            (l.target.id === d.id && l.source.id === n.id)
          );
          return isConnected ? 1 : 0.3;
        });
    }

    function handleMouseOut(e, d) {
      d3.select(this).attr("stroke", "rgba(255,255,255,0.35)").attr("stroke-width", 0.8);
      
      // Hide label if function/import
      if (!['file', 'class'].includes(d.type)) {
        d3.select(this.parentNode).select(".node-label").style("visibility", "hidden");
      }

      // If a node is currently clicked/selected, don't revert opacities
      if (!selectedNode) {
        svg.selectAll('.graph-link').style("opacity", 0.35);
        svg.selectAll('.graph-node').style("opacity", 1);
      } else {
        // Re-apply the selection state opacities
        svg.selectAll('.graph-node').style("opacity", n => n.id === selectedNode.id ? 1 : 0.2);
        svg.selectAll('.graph-link').style("opacity", l => 
          (l.source.id === selectedNode.id || l.target.id === selectedNode.id) ? 1 : 0.05
        );
      }
    }

    return () => {
      simulation.stop();
      svg.selectAll("*").remove();
    };
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '600px' }}>
      
      {/* Container for the D3 SVG */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Glassmorphic Legend */}
      <div className="d3-legend">
        <div className="legend-item"><span className="dot file-dot"></span> File</div>
        <div className="legend-item"><span className="dot class-dot"></span> Class</div>
        <div className="legend-item"><span className="dot fn-dot"></span> Function</div>
        <div className="legend-item"><span className="dot imp-dot"></span> Import</div>
      </div>

      {/* Glassmorphic Detail Panel */}
      {selectedNode && (
        <div className="d3-detail-panel">
          <div className="d3-detail-header">
            <span className={`dot ${selectedNode.type}-dot`}></span>
            <span className="d3-detail-title">{selectedNode.label || selectedNode.id}</span>
          </div>
          
          <div className="d3-detail-section">
            <h4>Outgoing ({selectedNode.outgoing.length})</h4>
            {selectedNode.outgoing.length === 0 && <span className="empty-text">None</span>}
            <ul>
              {selectedNode.outgoing.map((l, i) => (
                <li key={i}>
                  <span className="edge-kind">[{l.kind}]</span> {l.target.label || l.target.id || l.target}
                </li>
              ))}
            </ul>
          </div>

          <div className="d3-detail-section">
            <h4>Incoming ({selectedNode.incoming.length})</h4>
            {selectedNode.incoming.length === 0 && <span className="empty-text">None</span>}
            <ul>
              {selectedNode.incoming.map((l, i) => (
                <li key={i}>
                  <span className="edge-kind">[{l.kind}]</span> {l.source.label || l.source.id || l.source}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      
      <div className="d3-hint">drag to pan · scroll to zoom · click a node</div>
    </div>
  );
}
